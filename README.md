# 🐺 Optimizador de Imágenes

Aplicación de escritorio sencilla para **reducir el peso de tus imágenes**, **convertirlas a WebP / JPG / PNG**, **redimensionarlas** y, opcionalmente, **quitarles el fondo** con IA.

Funciona igual en **Windows, Mac y Linux** (se ejecuta con Python). Tiene una ventana con botones —no hace falta saber programar— y también un modo por línea de comandos para usuarios avanzados.

---

## ✨ Características

- 📁 Procesa una **carpeta completa** (incluye subcarpetas) o una **sola imagen**.
- 🔄 Convierte a **WebP**, **JPG** o **PNG**.
- 📐 **Redimensiona** a un ancho máximo (mantiene la proporción).
- 🎚️ Ajusta la **calidad** de compresión.
- 🎨 **Quita el fondo** con IA (se instala sola la primera vez).
- 💾 **No modifica tus originales**: guarda todo en tu carpeta de **Descargas**, en una carpeta nueva `*-optimized`.

---

## ✅ Requisitos

- **Python 3.10 o superior** ([descárgalo aquí](https://www.python.org/downloads/)).
- **Tkinter** (la interfaz gráfica):
  - 🪟 Windows y 🍎 Mac: ya viene incluido con el Python de python.org.
  - 🐧 Linux: instálalo con `sudo apt install python3-tk`.

---

## 📦 Instalación

1. Descarga o clona este proyecto:
   ```bash
   git clone https://github.com/KevinGil7/Optimizador_img.git
   cd Optimizador_img
   ```
2. Instala las dependencias:
   ```bash
   # Windows
   py -m pip install -r requirements.txt
   # Mac / Linux
   python3 -m pip install -r requirements.txt
   ```
   Eso instala **Pillow** (lo único obligatorio). La función de **quitar fondo** (`rembg`) se instala **automáticamente** la primera vez que la usas.

---

## 🚀 Cómo usarlo

### 1) La aplicación de escritorio (recomendada para todos) 🪟🍎🐧

La misma ventana funciona en los tres sistemas; solo cambia el comando para abrirla:

| Sistema       | Cómo abrirla                                                                       |
| ------------- | ---------------------------------------------------------------------------------- |
| 🪟 **Windows** | **`py optimizar_imagenes_app.py`** &nbsp;·&nbsp; o **doble clic** en `Optimizar Imagenes.bat` |
| 🍎 **Mac**     | **`python3 optimizar_imagenes_app.py`**                                            |
| 🐧 **Linux**   | **`python3 optimizar_imagenes_app.py`**                                            |

Luego, dentro de la ventana:

1. Clic en **📁 Carpeta** o **🖼️ Imagen** para elegir desde tu explorador de archivos.
2. Marca las opciones (formato, ancho, calidad, quitar fondo).
3. Clic en **✨ Optimizar imágenes**.
4. Al terminar te pregunta si quieres **abrir la carpeta** con los resultados.

> 💡 **`py` vs `python3`:** en **Windows** el comando es **`py`**; en **Mac/Linux** es **`python3`**.
> Si Windows te dice *"Python was not found… Microsoft Store"*, es que **no tienes Python instalado** —
> instálalo desde [python.org](https://www.python.org/downloads/) (marca *"Add python.exe to PATH"*).

### 2) Modo asistente en la terminal 💬

Ejecuta el script **sin argumentos** y te irá preguntando paso a paso:

```bash
py optimize_images.py            # Windows
python3 optimize_images.py       # Mac / Linux
```

### 3) Línea de comandos (avanzado) ⌨️

```bash
py optimize_images.py --source ./fotos --format webp --remove-bg --max-width 1600 --quality 80
```

| Argumento        | Descripción                                   | Valor por defecto              |
| ---------------- | --------------------------------------------- | ------------------------------ |
| `--source`       | Carpeta **o** imagen a procesar               | *(obligatorio en este modo)*   |
| `--format`       | `webp`, `jpg` o `png`                         | *(obligatorio en este modo)*   |
| `--max-width`    | Ancho máximo en píxeles                       | `1600`                         |
| `--quality`      | Calidad de 1 a 100                            | `80`                           |
| `--remove-bg`    | Quita el fondo (requiere `rembg`)             | desactivado                    |
| `--extensions`   | Extensiones a buscar                          | `.jpg .jpeg .png .webp`        |

> 💡 Si pasas `--source` y `--format`, corre en modo automático. Si no, entra al modo asistente.

---

## ❓ Preguntas frecuentes

**¿Dónde quedan las imágenes optimizadas?**
En tu carpeta de **Descargas**, dentro de una carpeta nueva terminada en `-optimized`
(por ejemplo `Descargas/GORRA_KINDER-optimized`). Así son fáciles de encontrar.

**¿Toca mis imágenes originales?**
No. Tus originales quedan intactos; los resultados se guardan aparte en Descargas.

**Marqué "quitar fondo" y la primera vez tardó bastante.**
Es normal: la primera vez descarga `rembg` (~100 MB) y un modelo de IA (~170 MB). Verás el avance en vivo en el panel de resultados. Las siguientes veces ya es rápido.

**¿Qué formato elijo?**
**WebP** es el mejor para la web (menos peso, soporta transparencia). Usa **JPG** para fotos sin transparencia (si quitas el fondo, este saldrá **blanco**) y **PNG** si necesitas transparencia con máxima compatibilidad.

---

## 📁 Archivos del proyecto

| Archivo                       | Para qué sirve                                       |
| ----------------------------- | ---------------------------------------------------- |
| `optimizar_imagenes_app.py`   | La aplicación de escritorio (ventana).               |
| `optimize_images.py`          | La lógica de optimización + modo terminal/asistente. |
| `Optimizar Imagenes.bat`      | Abre la app con doble clic en Windows.               |
| `logo.png`                    | Logo de la aplicación.                               |
| `requirements.txt`            | Dependencias de Python.                              |

---

## 📝 Licencia

Uso libre. Adáptalo a tus necesidades.
