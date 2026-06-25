"""
Optimizador de Imágenes - Aplicación de escritorio
==================================================
Ventana sencilla para que cualquiera pueda:
  - Elegir una carpeta o una imagen con un clic
  - Convertir a WebP / JPG / PNG
  - Reducir el peso y el ancho
  - (Opcional) Quitar el fondo

Reutiliza la lógica de optimize_images.py.

Ejecutar (Windows):  py optimizar_imagenes_app.py
Ejecutar (Mac/Linux): python3 optimizar_imagenes_app.py
"""

import importlib.util
import os
import platform
import queue
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

# Reutilizamos la lógica que ya tienes en optimize_images.py
from optimize_images import collect_entries, optimize_image

EXTENSIONS = [".jpg", ".jpeg", ".png", ".webp"]


def _ruta_recurso(nombre: str) -> Path:
    """Ruta a un archivo de recursos junto al script (logo, etc.)."""
    return Path(__file__).resolve().parent / nombre


# ------------------------------------------------------- rembg (quitar fondo)
# En Windows evitamos que aparezca una ventana de consola al llamar a pip.
_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


def rembg_disponible() -> bool:
    """¿Se puede importar rembg en este Python?"""
    try:
        return importlib.util.find_spec("rembg") is not None
    except Exception:
        return False


def _instalar_rembg(log) -> bool:
    """Instala rembg + onnxruntime en este Python, mostrando el avance en vivo."""
    cmd = [sys.executable, "-m", "pip", "install", "rembg", "onnxruntime"]
    # Pedimos a pip que imprima el progreso línea por línea (y sin barra animada de pip).
    entorno = {**os.environ, "PIP_PROGRESS_BAR": "off", "PYTHONUNBUFFERED": "1"}
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, bufsize=1, creationflags=_NO_WINDOW, env=entorno)
        ultimas = []
        for linea in proc.stdout:
            s = linea.strip()
            ultimas.append(s)
            ultimas = ultimas[-25:]
            # Mostramos solo las líneas significativas (qué se descarga/instala).
            if s.startswith(("Collecting ", "Downloading ", "Building ", "Preparing ",
                             "Installing collected", "Successfully installed")):
                log("   " + (s[:70] + "…" if len(s) > 71 else s))
        proc.wait()
        if proc.returncode != 0:
            log("❌ Error al instalar rembg:")
            for s in ultimas[-8:]:
                if s:
                    log("   " + s)
            return False
        return True
    except Exception as e:  # noqa: BLE001
        log(f"❌ No se pudo instalar rembg: {e}")
        return False


def preparar_quitafondo(log, on_install_start=None, on_install_end=None):
    """Valida rembg (lo instala si falta) y devuelve una función quitar(src)->PNG.

    Orden: 1) si ya está, se usa; 2) si no, se instala. Devuelve None si no se pudo.
    rembg corre EN ESTE proceso (más rápido para varias imágenes: la sesión de IA
    se crea una sola vez).
    """
    if rembg_disponible():
        log("✅ 'rembg' ya está disponible: se usará para quitar el fondo.")
    else:
        log("⏳ No se encontró 'rembg'. Instalando por única vez (~100 MB, puede tardar)…")
        if on_install_start:
            on_install_start()
        ok = _instalar_rembg(log)
        if on_install_end:
            on_install_end()
        importlib.invalidate_caches()
        if not ok or not rembg_disponible():
            log("❌ No se pudo preparar 'rembg' para quitar el fondo.")
            return None
        log("✅ 'rembg' instalado correctamente.")

    try:
        from rembg import remove
    except Exception as e:  # noqa: BLE001
        log(f"❌ No se pudo cargar 'rembg': {e}")
        return None

    def quitar(src: Path) -> Path | None:
        try:
            with Image.open(src) as im:
                recorte = remove(im)
            out = Path(tempfile.gettempdir()) / f"cutout_{abs(hash(str(src))) & 0xFFFFFFFF}.png"
            recorte.save(out, "PNG")
            return out
        except Exception as e:  # noqa: BLE001
            log(f"⚠️  No se pudo quitar el fondo de {src.name}: {e}")
            return None

    return quitar


def _carpeta_descargas() -> Path:
    """Carpeta de Descargas del usuario (destino fijo, fácil de encontrar)."""
    candidata = Path.home() / "Downloads"
    if candidata.exists():
        return candidata
    # Windows: por si la carpeta de Descargas fue movida de sitio.
    try:
        import winreg
        clave = r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, clave) as k:
            val, _ = winreg.QueryValueEx(k, "{374DE290-123F-4565-9164-39C4925E467B}")
            p = Path(os.path.expandvars(val))
            if p.exists():
                return p
    except Exception:
        pass
    return Path.home()


# ============================================================== Paleta
# Tema oscuro: acento NEGRO, ventana GRIS, salida con colores que resaltan.
COL_BG = "#3C3F45"         # fondo de la ventana (gris)
COL_CARD = "#33363B"       # tarjetas (gris más oscuro, da profundidad)
COL_PRIMARY = "#111317"    # acento NEGRO
COL_PRIMARY_DK = "#2A2E36"  # hover del botón (negro aclarado)
COL_GRAD_A = "#0B0C0F"     # degradado encabezado (negro)
COL_GRAD_B = "#33363B"     # degradado encabezado (gris)
COL_TEXT = "#ECEEF2"       # texto principal (claro)
COL_MUTED = "#A6ACB6"      # texto secundario
COL_BORDER = "#4A4E55"     # bordes suaves
COL_TRACK = "#26282D"      # pistas (segmento)
COL_CONSOLE = "#0A0B0D"    # fondo del panel de resultados (negro)
COL_PROGRESS = "#3FB950"   # relleno de la barra de progreso (verde, resalta)

# Colores de la consola de resultados (resaltan sobre negro)
COL_OK = "#3FB950"         # verde
COL_ERR = "#F85149"        # rojo
COL_WARN = "#E3B341"       # amarillo
COL_HEAD = "#58A6FF"       # azul (encabezados/resumen)
COL_LOG = "#C9D1D9"        # texto normal


# ====================================================== Utilidades de dibujo
def _round_rect(canvas: tk.Canvas, x1, y1, x2, y2, r, **kw):
    """Dibuja un rectángulo de esquinas redondeadas en un Canvas."""
    pts = [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
        x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    ]
    return canvas.create_polygon(pts, smooth=True, **kw)


def _hex_to_rgb(h: str):
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _rgb_to_hex(rgb) -> str:
    return "#%02x%02x%02x" % rgb


def _blend(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


# ====================================================== Widgets personalizados
class GradientHeader(tk.Canvas):
    """Encabezado con degradado horizontal, logo, título y subtítulo."""

    def __init__(self, parent, *, c1, c2, height=96, title="", subtitle="", logo_path=None):
        super().__init__(parent, height=height, highlightthickness=0, bd=0)
        self.c1, self.c2 = _hex_to_rgb(c1), _hex_to_rgb(c2)
        self.title, self.subtitle = title, subtitle
        self._logo = None
        self._logo_w = 0
        if logo_path and Path(logo_path).exists():
            try:
                target_h = height - 34
                img = Image.open(logo_path)
                ratio = target_h / img.height
                img = img.resize((max(1, round(img.width * ratio)), target_h), Image.LANCZOS)
                self._logo = ImageTk.PhotoImage(img)
                self._logo_w = img.width
            except Exception:
                self._logo = None
        self.bind("<Configure>", lambda e: self._draw())

    def _draw(self):
        self.delete("all")
        w = self.winfo_width()
        h = int(self["height"])
        if w <= 1:
            return
        for x in range(w):
            col = _rgb_to_hex(_blend(self.c1, self.c2, x / (w - 1)))
            self.create_line(x, 0, x, h, fill=col)
        x_text = 30
        if self._logo is not None:
            self.create_image(26, h // 2, anchor="w", image=self._logo)
            x_text = 26 + self._logo_w + 20
        self.create_text(x_text, h // 2 - 13, anchor="w", text=self.title,
                         fill="#FFFFFF", font=("Segoe UI", 19, "bold"))
        self.create_text(x_text + 1, h // 2 + 16, anchor="w", text=self.subtitle,
                         fill="#E9EAFF", font=("Segoe UI", 10))


class RoundedButton(tk.Canvas):
    """Botón redondeado con efecto hover."""

    def __init__(self, parent, text="", command=None, *, parent_bg,
                 bg, fg, hover_bg, font=("Segoe UI", 11, "bold"),
                 radius=14, padx=20, pady=12, fixed_width=None,
                 disabled_bg="#C7CCDE", disabled_fg="#EFF0F7"):
        self._font = tkfont.Font(font=font)
        h = self._font.metrics("linespace") + pady * 2
        w = fixed_width if fixed_width else self._font.measure(text) + padx * 2
        super().__init__(parent, width=w, height=h, bg=parent_bg,
                         highlightthickness=0, bd=0)
        self.command = command
        self.text, self.fg, self.bg, self.hover_bg = text, fg, bg, hover_bg
        self.radius, self.disabled_bg, self.disabled_fg = radius, disabled_bg, disabled_fg
        self._enabled, self._hover = True, False
        self.bind("<Configure>", lambda e: self._draw())
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)
        self._draw()

    def _draw(self):
        self.delete("all")
        w = self.winfo_width() or self.winfo_reqwidth()
        h = self.winfo_height() or self.winfo_reqheight()
        if not self._enabled:
            fill, fg = self.disabled_bg, self.disabled_fg
        else:
            fill, fg = (self.hover_bg if self._hover else self.bg), self.fg
        _round_rect(self, 1, 1, w - 1, h - 1, self.radius, fill=fill, outline=fill)
        self.create_text(w // 2, h // 2, text=self.text, fill=fg, font=self._font)

    def _on_enter(self, _):
        if self._enabled:
            self._hover = True
            self._draw()
            self.config(cursor="hand2")

    def _on_leave(self, _):
        self._hover = False
        self._draw()

    def _on_click(self, _):
        if self._enabled and self.command:
            self.command()

    def set_text(self, t):
        self.text = t
        self._draw()

    def set_enabled(self, b):
        self._enabled = b
        self._hover = False
        self._draw()
        self.config(cursor="hand2" if b else "arrow")


class ToggleSwitch(tk.Canvas):
    """Interruptor on/off estilo moderno."""

    def __init__(self, parent, variable, *, parent_bg, on_color,
                 off_color="#CBD2E6", command=None):
        super().__init__(parent, width=56, height=30, bg=parent_bg,
                         highlightthickness=0, bd=0)
        self.var, self.on_color, self.off_color = variable, on_color, off_color
        self.command = command
        self.config(cursor="hand2")
        self.bind("<Button-1>", self._toggle)
        self._draw()

    def _draw(self):
        self.delete("all")
        on = bool(self.var.get())
        col = self.on_color if on else self.off_color
        _round_rect(self, 2, 5, 54, 27, 11, fill=col, outline=col)
        cx = 42 if on else 16
        self.create_oval(cx - 9, 7, cx + 9, 25, fill="#FFFFFF", outline="#EBEEF7")

    def _toggle(self, _):
        self.var.set(not self.var.get())
        self._draw()
        if self.command:
            self.command()


class SegmentedControl(tk.Canvas):
    """Selector de una opción estilo 'segmento' (pestañas tipo pill)."""

    def __init__(self, parent, options, variable, *, parent_bg,
                 font=("Segoe UI", 10, "bold"), seg_pad=24, height=40, command=None):
        self._font = tkfont.Font(font=font)
        self.options, self.var, self.command = options, variable, command
        self.pad = 4
        self.seg_w = max(self._font.measure(lab) for _, lab in options) + seg_pad * 2
        w = self.seg_w * len(options) + self.pad * 2
        super().__init__(parent, width=w, height=height, bg=parent_bg,
                         highlightthickness=0, bd=0)
        self.config(cursor="hand2")
        self.bind("<Button-1>", self._click)
        self._draw()

    def _draw(self):
        self.delete("all")
        w, h = int(self["width"]), int(self["height"])
        _round_rect(self, 0, 0, w, h, h // 2, fill=COL_TRACK, outline=COL_TRACK)
        cur = self.var.get()
        for i, (val, lab) in enumerate(self.options):
            x0 = self.pad + i * self.seg_w
            x1 = x0 + self.seg_w
            sel = (val == cur)
            if sel:
                _round_rect(self, x0 + 1, 3, x1 - 1, h - 3, (h - 6) // 2,
                            fill=COL_PRIMARY, outline=COL_BORDER)
            self.create_text((x0 + x1) // 2, h // 2, text=lab,
                             fill=COL_TEXT if sel else COL_MUTED, font=self._font)

    def _click(self, e):
        idx = int((e.x - self.pad) // self.seg_w)
        idx = max(0, min(len(self.options) - 1, idx))
        val = self.options[idx][0]
        if val != self.var.get():
            self.var.set(val)
            self._draw()
            if self.command:
                self.command()


class RoundedProgress(tk.Canvas):
    """Barra de progreso redondeada (modo normal y modo animado 'trabajando')."""

    def __init__(self, parent, *, parent_bg, height=14):
        super().__init__(parent, height=height, bg=parent_bg,
                         highlightthickness=0, bd=0)
        self.maximum, self.value = 100, 0
        self._pulse = False
        self._pulse_pos = 0.0
        self.bind("<Configure>", lambda e: self._draw())

    def set_max(self, m):
        self.maximum = max(1, m)
        self._draw()

    def set_value(self, v):
        self.value = v
        self._draw()

    def _draw(self):
        if self._pulse:
            return
        self.delete("all")
        w = self.winfo_width()
        h = int(self["height"])
        if w <= 1:
            return
        r = h // 2
        _round_rect(self, 0, 0, w, h, r, fill=COL_TRACK, outline=COL_TRACK)
        frac = min(1.0, max(0.0, self.value / self.maximum))
        if frac > 0:
            fw = max(h, int(w * frac))
            _round_rect(self, 0, 0, fw, h, r, fill=COL_PROGRESS, outline=COL_PROGRESS)

    # --- Modo animado (indeterminado): un segmento que va y viene ---
    def start_pulse(self):
        self._pulse = True
        self._pulse_pos = 0.0
        self._animate_pulse()

    def stop_pulse(self):
        self._pulse = False
        self._draw()

    def _animate_pulse(self):
        if not self._pulse:
            return
        self._pulse_pos = (self._pulse_pos + 0.035) % 1.0
        self.delete("all")
        w = self.winfo_width()
        h = int(self["height"])
        if w > 1:
            r = h // 2
            _round_rect(self, 0, 0, w, h, r, fill=COL_TRACK, outline=COL_TRACK)
            seg = max(h, int(w * 0.30))
            travel = max(1, w - seg)
            t = self._pulse_pos * 2
            if t > 1:
                t = 2 - t  # ping-pong 0→1→0
            x = int(travel * t)
            _round_rect(self, x, 0, x + seg, h, r, fill=COL_PROGRESS, outline=COL_PROGRESS)
        self.after(40, self._animate_pulse)


# ============================================================== Aplicación
class OptimizadorApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Optimizador de Imágenes")
        self.root.geometry("820x900")
        self.root.minsize(740, 820)
        self.root.configure(bg=COL_BG)

        self.cola: queue.Queue = queue.Queue()
        self.procesando = False

        self._aplicar_estilo()
        self._construir_interfaz()
        self.root.after(100, self._revisar_cola)

    # --------------------------------------------------------------- estilo
    def _aplicar_estilo(self) -> None:
        st = ttk.Style()
        try:
            st.theme_use("clam")
        except tk.TclError:
            pass
        st.configure("Campo.TEntry", fieldbackground=COL_TRACK, foreground=COL_TEXT,
                     insertcolor=COL_TEXT, bordercolor=COL_BORDER, lightcolor=COL_BORDER,
                     darkcolor=COL_BORDER, borderwidth=1, padding=6)
        st.configure("Campo.TSpinbox", fieldbackground=COL_TRACK, foreground=COL_TEXT,
                     insertcolor=COL_TEXT, bordercolor=COL_BORDER, lightcolor=COL_BORDER,
                     darkcolor=COL_BORDER, borderwidth=1, arrowsize=13, padding=5)
        st.map("Campo.TSpinbox", fieldbackground=[("readonly", COL_TRACK)])
        st.configure("Calidad.Horizontal.TScale", background="#C8CCD2",
                     troughcolor=COL_TRACK, bordercolor=COL_CARD)
        st.configure("Log.Vertical.TScrollbar", background="#4A4E55",
                     troughcolor=COL_CONSOLE, bordercolor=COL_CONSOLE,
                     arrowcolor=COL_TEXT)
        st.map("Log.Vertical.TScrollbar", background=[("active", "#5C616A")])

    # ------------------------------------------------------------- tarjetas
    def _card(self, parent, numero, titulo, subtitulo=None) -> tk.Frame:
        """Crea una tarjeta blanca con badge numerado y devuelve el cuerpo."""
        wrap = tk.Frame(parent, bg=COL_BORDER)
        wrap.pack(fill="x", pady=(0, 16))
        card = tk.Frame(wrap, bg=COL_CARD)
        card.pack(fill="x", padx=1, pady=1)
        inner = tk.Frame(card, bg=COL_CARD)
        inner.pack(fill="x", padx=22, pady=18)

        row = tk.Frame(inner, bg=COL_CARD)
        row.pack(fill="x")
        badge = tk.Canvas(row, width=30, height=30, bg=COL_CARD, highlightthickness=0, bd=0)
        badge.pack(side="left")
        badge.create_oval(3, 3, 27, 27, fill=COL_PRIMARY, outline=COL_PRIMARY)
        badge.create_text(15, 15, text=str(numero), fill="#FFFFFF",
                          font=("Segoe UI", 11, "bold"))
        tk.Label(row, text="   " + titulo, bg=COL_CARD, fg=COL_TEXT,
                 font=("Segoe UI", 12, "bold")).pack(side="left")

        if subtitulo:
            tk.Label(inner, text=subtitulo, bg=COL_CARD, fg=COL_MUTED,
                     font=("Segoe UI", 9)).pack(anchor="w", pady=(6, 0))

        body = tk.Frame(inner, bg=COL_CARD)
        body.pack(fill="x", pady=(14, 0))
        return body

    def _fila(self, body, etiqueta) -> tk.Frame:
        fila = tk.Frame(body, bg=COL_CARD)
        fila.pack(fill="x", pady=7)
        tk.Label(fila, text=etiqueta, bg=COL_CARD, fg=COL_TEXT, width=15, anchor="w",
                 font=("Segoe UI", 10)).pack(side="left")
        return fila

    # ------------------------------------------------------------------ UI
    def _construir_interfaz(self) -> None:
        # Encabezado con degradado y logo
        GradientHeader(self.root, c1=COL_GRAD_A, c2=COL_GRAD_B, height=96,
                       logo_path=_ruta_recurso("logo.png"),
                       title="Optimizador de Imágenes",
                       subtitle="Reduce el peso, cambia el formato y quita el fondo — fácil y rápido."
                       ).pack(fill="x")

        outer = tk.Frame(self.root, bg=COL_BG)
        outer.pack(fill="both", expand=True)
        cont = tk.Frame(outer, bg=COL_BG)
        cont.pack(fill="both", expand=True, padx=24, pady=(20, 16))

        # --- 1) Origen ---
        b1 = self._card(cont, 1, "¿Qué quieres optimizar?",
                        "Elige una carpeta completa o una sola imagen.")
        self.var_ruta = tk.StringVar()
        fila = tk.Frame(b1, bg=COL_CARD)
        fila.pack(fill="x")
        ttk.Entry(fila, textvariable=self.var_ruta, style="Campo.TEntry",
                  font=("Segoe UI", 10)).pack(side="left", fill="x", expand=True, ipady=3)
        RoundedButton(fila, text="📁  Carpeta", command=self._elegir_carpeta,
                      parent_bg=COL_CARD, bg="#50545B", fg=COL_TEXT, hover_bg="#5C616A",
                      font=("Segoe UI", 10, "bold"), radius=10, padx=14, pady=9
                      ).pack(side="left", padx=(10, 0))
        RoundedButton(fila, text="🖼️  Imagen", command=self._elegir_imagen,
                      parent_bg=COL_CARD, bg="#50545B", fg=COL_TEXT, hover_bg="#5C616A",
                      font=("Segoe UI", 10, "bold"), radius=10, padx=14, pady=9
                      ).pack(side="left", padx=(8, 0))

        # --- 2) Opciones ---
        b2 = self._card(cont, 2, "Opciones")

        # Formato (segmentado)
        f_fmt = self._fila(b2, "Formato")
        self.var_formato = tk.StringVar(value="WEBP")
        SegmentedControl(f_fmt, [("WEBP", "WebP"), ("JPG", "JPG"), ("PNG", "PNG")],
                         self.var_formato, parent_bg=COL_CARD).pack(side="left")
        tk.Label(f_fmt, text="WebP recomendado para web", bg=COL_CARD, fg=COL_MUTED,
                 font=("Segoe UI", 9)).pack(side="left", padx=(12, 0))

        # Quitar fondo (toggle)
        f_bg = self._fila(b2, "Quitar el fondo")
        self.var_fondo = tk.BooleanVar(value=False)
        ToggleSwitch(f_bg, self.var_fondo, parent_bg=COL_CARD,
                     on_color=COL_PRIMARY).pack(side="left")
        tk.Label(f_bg, text="Se instala automáticamente la 1ª vez", bg=COL_CARD,
                 fg=COL_MUTED, font=("Segoe UI", 9)).pack(side="left", padx=(12, 0))

        # Ancho máximo
        f_w = self._fila(b2, "Ancho máximo")
        self.var_ancho = tk.IntVar(value=1600)
        ttk.Spinbox(f_w, from_=100, to=10000, increment=100, textvariable=self.var_ancho,
                    width=9, style="Campo.TSpinbox", font=("Segoe UI", 10)).pack(side="left")
        tk.Label(f_w, text="píxeles", bg=COL_CARD, fg=COL_MUTED,
                 font=("Segoe UI", 9)).pack(side="left", padx=(8, 0))

        # Calidad
        f_q = self._fila(b2, "Calidad")
        self.var_calidad = tk.IntVar(value=80)
        # IMPORTANTE: el label debe existir ANTES que la escala, porque ttk.Scale
        # dispara su 'command' al asignar el valor inicial (en macOS pasa de inmediato).
        self.lbl_calidad = tk.Label(f_q, text="80%", bg=COL_CARD, fg=COL_OK,
                                    width=5, anchor="e", font=("Segoe UI", 11, "bold"))
        escala = ttk.Scale(f_q, from_=1, to=100, orient="horizontal",
                           style="Calidad.Horizontal.TScale",
                           command=self._actualizar_calidad)
        escala.set(80)
        escala.pack(side="left", fill="x", expand=True, padx=(0, 12))
        self.lbl_calidad.pack(side="left")

        # --- Botón principal ---
        self.btn_optimizar = RoundedButton(
            cont, text="✨   Optimizar imágenes", command=self._iniciar,
            parent_bg=COL_BG, bg=COL_PRIMARY, fg="#FFFFFF", hover_bg=COL_PRIMARY_DK,
            font=("Segoe UI", 13, "bold"), radius=16, pady=15, fixed_width=320)
        self.btn_optimizar.pack(fill="x", pady=(2, 10))

        self.barra = RoundedProgress(cont, parent_bg=COL_BG)
        self.barra.pack(fill="x")
        self.var_estado = tk.StringVar(value="Listo para empezar.")
        tk.Label(cont, textvariable=self.var_estado, bg=COL_BG, fg=COL_MUTED,
                 font=("Segoe UI", 9, "italic")).pack(anchor="w", pady=(6, 0))

        # --- Resultado ---
        tk.Label(cont, text="Resultado", bg=COL_BG, fg=COL_TEXT,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(10, 5))
        marco_log = tk.Frame(cont, bg=COL_BORDER)
        marco_log.pack(fill="both", expand=True)
        log_inner = tk.Frame(marco_log, bg=COL_CONSOLE)
        log_inner.pack(fill="both", expand=True, padx=1, pady=1)
        self.txt_log = tk.Text(log_inner, height=14, wrap="word", state="disabled",
                               font=("Consolas", 9), bg=COL_CONSOLE, fg=COL_LOG,
                               insertbackground=COL_LOG, relief="flat",
                               padx=12, pady=10, borderwidth=0)
        scroll = ttk.Scrollbar(log_inner, command=self.txt_log.yview,
                               style="Log.Vertical.TScrollbar")
        self.txt_log.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.txt_log.pack(side="left", fill="both", expand=True)
        # Colores de los mensajes
        self.txt_log.tag_configure("ok", foreground=COL_OK)
        self.txt_log.tag_configure("err", foreground=COL_ERR)
        self.txt_log.tag_configure("warn", foreground=COL_WARN)
        self.txt_log.tag_configure("head", foreground=COL_HEAD)
        self.txt_log.tag_configure("normal", foreground=COL_LOG)
        self._log("👋 ¡Hola! Elige una carpeta o imagen y presiona «Optimizar imágenes».")

    # -------------------------------------------------------------- acciones
    def _elegir_carpeta(self) -> None:
        ruta = filedialog.askdirectory(title="Selecciona una carpeta con imágenes")
        if ruta:
            self.var_ruta.set(ruta)

    def _elegir_imagen(self) -> None:
        ruta = filedialog.askopenfilename(
            title="Selecciona una imagen",
            filetypes=[("Imágenes", "*.jpg *.jpeg *.png *.webp"), ("Todos", "*.*")],
        )
        if ruta:
            self.var_ruta.set(ruta)

    def _actualizar_calidad(self, valor: str) -> None:
        q = int(round(float(valor)))
        self.var_calidad.set(q)
        # Blindaje: el callback puede dispararse durante la construcción (macOS).
        if hasattr(self, "lbl_calidad"):
            self.lbl_calidad.configure(text=f"{q}%")

    def _log(self, texto: str) -> None:
        s = texto.lstrip()
        if s.startswith("✅"):
            tag = "ok"
        elif s.startswith("❌"):
            tag = "err"
        elif s.startswith(("⚠", "⏳")):
            tag = "warn"
        elif s.startswith(("📊", "=", "📂")):
            tag = "head"
        else:
            tag = "normal"
        self.txt_log.configure(state="normal")
        self.txt_log.insert("end", texto + "\n", tag)
        self.txt_log.see("end")
        self.txt_log.configure(state="disabled")

    def _limpiar_log(self) -> None:
        self.txt_log.configure(state="normal")
        self.txt_log.delete("1.0", "end")
        self.txt_log.configure(state="disabled")

    # -------------------------------------------------------------- proceso
    def _iniciar(self) -> None:
        if self.procesando:
            return

        ruta_txt = self.var_ruta.get().strip().strip('"').strip("'")
        if not ruta_txt:
            messagebox.showwarning("Falta la ruta", "Elige una carpeta o una imagen primero.")
            return

        source = Path(ruta_txt)
        if not source.exists():
            messagebox.showerror("Ruta no encontrada", f"No existe:\n{source}")
            return

        entries = collect_entries(source, EXTENSIONS)
        if not entries:
            messagebox.showerror(
                "Sin imágenes",
                f"No se encontraron imágenes ({', '.join(EXTENSIONS)}) en:\n{source}",
            )
            return

        formato = self.var_formato.get()
        try:
            ancho = int(self.var_ancho.get())
        except Exception:
            ancho = 1600
        calidad = self.var_calidad.get()
        fondo = self.var_fondo.get()

        # Carpeta de salida: SIEMPRE en Descargas (fácil de encontrar).
        if source.is_file():
            base_dir = source.parent
            nombre = source.stem
        else:
            base_dir = source
            nombre = source.name
        output_dir = _carpeta_descargas() / f"{nombre}-optimized"

        suffix = {"WEBP": ".webp", "PNG": ".png", "JPG": ".jpg"}[formato]

        self._limpiar_log()
        self._log(f"✨ Procesando {len(entries)} imagen(es)…")
        self._log(f"   Origen : {source}")
        self._log(f"   Destino: {output_dir}")
        self._log(f"   Formato: {formato} | Ancho: {ancho}px | Calidad: {calidad}%"
                  + ("  | Quitar fondo: Sí" if fondo else ""))
        if fondo and formato == "JPG":
            self._log("⚠️  JPG no admite transparencia: el fondo quedará BLANCO. "
                      "Usa WebP o PNG si lo quieres transparente.")
        self._log("")

        self.procesando = True
        self.btn_optimizar.set_enabled(False)
        self.btn_optimizar.set_text("⏳   Procesando…")
        self.var_estado.set(f"Procesando {len(entries)} imagen(es)…")
        self.barra.set_max(len(entries))
        self.barra.set_value(0)

        hilo = threading.Thread(
            target=self._trabajar,
            args=(entries, base_dir, output_dir, suffix, formato, ancho, calidad, fondo),
            daemon=True,
        )
        hilo.start()

    def _trabajar(self, entries, base_dir, output_dir, suffix, formato, ancho, calidad, fondo) -> None:
        """Se ejecuta en un hilo aparte para no congelar la ventana."""
        def _log(t):
            self.cola.put(("log", t))

        # Si se pidió quitar el fondo, validamos rembg (o lo instalamos) antes de empezar.
        quitar_fondo = None
        if fondo:
            quitar_fondo = preparar_quitafondo(
                _log,
                on_install_start=lambda: self.cola.put(("pulse_on", None)),
                on_install_end=lambda: self.cola.put(("pulse_off", None)),
            )
            if quitar_fondo is None:
                self.cola.put(("log", "⚠️  Se continuará SIN quitar el fondo."))
                fondo = False
            self.cola.put(("log", ""))

        n = len(entries)
        total_antes = 0
        total_despues = 0
        errores = 0

        for i, src in enumerate(entries, start=1):
            rel = src.relative_to(base_dir)
            destino = output_dir / rel.with_suffix(suffix)
            temp = None
            try:
                fuente = src
                if fondo and quitar_fondo:
                    self.cola.put(("estado", f"Quitando fondo… {i}/{n}"))
                    temp = quitar_fondo(src)
                    if temp:
                        fuente = temp
                self.cola.put(("estado", f"Optimizando… {i}/{n} ({int(100 * i / n)}%)"))
                antes = src.stat().st_size  # peso del ORIGINAL (no del recorte temporal)
                _, despues = optimize_image(fuente, destino, formato, ancho, calidad, False)
                total_antes += antes
                total_despues += despues
                pct = 100 * despues / antes if antes else 0
                self.cola.put(("log", f"  ✅ {str(rel):<45} {antes:>9,} → {despues:>9,} B ({pct:.0f}%)"))
            except Exception as e:  # noqa: BLE001
                errores += 1
                self.cola.put(("log", f"  ❌ {rel}: {e}"))
            finally:
                if temp and temp.exists():
                    try:
                        temp.unlink()
                    except Exception:
                        pass
            self.cola.put(("progreso", (i, n)))

        self.cola.put(("fin", (total_antes, total_despues, len(entries), errores, output_dir)))

    def _revisar_cola(self) -> None:
        """Procesa mensajes del hilo de trabajo en el hilo de la interfaz."""
        try:
            while True:
                tipo, dato = self.cola.get_nowait()
                if tipo == "log":
                    self._log(dato)
                elif tipo == "progreso":
                    i, n = dato
                    self.barra.set_max(n)
                    self.barra.set_value(i)
                elif tipo == "estado":
                    self.var_estado.set(dato)
                elif tipo == "pulse_on":
                    self.barra.start_pulse()
                    self.var_estado.set("⏳ Instalando 'rembg' (una sola vez)… descargando…")
                elif tipo == "pulse_off":
                    self.barra.stop_pulse()
                elif tipo == "fin":
                    self._finalizar(*dato)
        except queue.Empty:
            pass
        self.root.after(100, self._revisar_cola)

    def _finalizar(self, total_antes, total_despues, n, errores, output_dir) -> None:
        self.procesando = False
        self.btn_optimizar.set_enabled(True)
        self.btn_optimizar.set_text("✨   Optimizar imágenes")

        reduccion = (100 * (total_antes - total_despues) / total_antes) if total_antes else 0
        self.var_estado.set(
            f"✅ Listo: {n - errores}/{n} imagen(es) · reducción {reduccion:.0f}%")
        self._log("")
        self._log("=" * 60)
        self._log("📊 RESUMEN")
        self._log(f"  Imágenes procesadas: {n - errores} / {n}")
        if errores:
            self._log(f"  Con error          : {errores}")
        self._log(f"  Peso original      : {total_antes / 1024 / 1024:.2f} MB")
        self._log(f"  Peso optimizado    : {total_despues / 1024 / 1024:.2f} MB")
        self._log(f"  Reducción          : {reduccion:.1f}%")
        self._log(f"  📂 Carpeta destino : {output_dir}")
        self._log("=" * 60)

        if messagebox.askyesno(
            "¡Listo!",
            f"Se optimizaron {n - errores} imagen(es).\n"
            f"Reducción: {reduccion:.1f}%\n\n¿Abrir la carpeta de destino?",
        ):
            self._abrir_carpeta(output_dir)

    @staticmethod
    def _abrir_carpeta(ruta: Path) -> None:
        """Abre la carpeta en el explorador (Windows / Mac / Linux)."""
        try:
            sistema = platform.system()
            if sistema == "Windows":
                os.startfile(ruta)  # type: ignore[attr-defined]
            elif sistema == "Darwin":  # macOS
                subprocess.run(["open", str(ruta)])
            else:  # Linux
                subprocess.run(["xdg-open", str(ruta)])
        except Exception:
            pass


def main() -> None:
    root = tk.Tk()
    try:
        # Mejor escalado en pantallas de alta resolución (solo Windows)
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    try:
        # Ícono de la ventana / barra de tareas (multiplataforma)
        root._icono = tk.PhotoImage(file=str(_ruta_recurso("logo.png")))
        root.iconphoto(True, root._icono)
    except Exception:
        pass
    OptimizadorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
