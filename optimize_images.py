import argparse
from pathlib import Path
from PIL import Image, ImageOps


def optimize_image(source_path: Path, target_path: Path, output_format: str, max_width: int, quality: int, remove_bg: bool = False) -> tuple[int, int]:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source_path) as img:
        img = ImageOps.exif_transpose(img)
        
        # Remove background if requested
        if remove_bg:
            try:
                from rembg import remove
                img = remove(img)
            except ImportError:
                print("⚠️  rembg no está instalado. Instala con: pip install rembg")
                print("   Continuando sin remover fondo...")
        
        # Resize if needed
        if max_width and img.width > max_width:
            ratio = max_width / float(img.width)
            new_height = round(img.height * ratio)
            img = img.resize((max_width, new_height), Image.LANCZOS)
        
        # Convert format
        fmt = output_format.upper()
        if fmt == "WEBP":
            img.save(target_path, format="WEBP", quality=quality, method=6)
        elif fmt == "JPG" or fmt == "JPEG":
            # JPG no soporta transparencia: si la imagen tiene canal alfa
            # (por ejemplo tras quitar el fondo), la componemos sobre BLANCO
            # en lugar de aplanarla sobre negro.
            if img.mode in ("RGBA", "LA", "P"):
                img = img.convert("RGBA")
                fondo_blanco = Image.new("RGBA", img.size, (255, 255, 255, 255))
                img = Image.alpha_composite(fondo_blanco, img).convert("RGB")
            img.save(target_path, format="JPEG", quality=quality, optimize=True)
        elif fmt == "PNG":
            img.save(target_path, format="PNG", optimize=True)
    
    return source_path.stat().st_size, target_path.stat().st_size


def ask_yes_no(question: str, default: bool = False) -> bool:
    """Pregunta s/n. Enter usa el valor por defecto."""
    hint = "S/n" if default else "s/N"
    while True:
        choice = input(f"{question} ({hint}): ").strip().lower()
        if choice == "":
            return default
        if choice in ("s", "si", "sí", "y", "yes"):
            return True
        if choice in ("n", "no"):
            return False
        print("   ❌ Responde s (sí) o n (no), o Enter para el valor por defecto.")


def collect_entries(source_path: Path, extensions: list[str]) -> list[Path]:
    """Devuelve la lista de imágenes a procesar.

    Acepta una sola imagen (devuelve esa imagen) o una carpeta
    (busca recursivamente todas las imágenes con las extensiones dadas).
    La comparación de extensiones no distingue mayúsculas/minúsculas.
    """
    exts = {e.lower() for e in extensions}
    if source_path.is_file():
        return [source_path] if source_path.suffix.lower() in exts else []

    entries = [p for p in source_path.rglob("*") if p.is_file() and p.suffix.lower() in exts]
    return sorted(set(entries))


def get_user_input() -> tuple[Path, str, int, int, bool]:
    # 1) Ruta: acepta una CARPETA o una sola IMAGEN
    print("\n📁 Arrastra aquí la carpeta o la imagen, o pega la ruta.")
    while True:
        source = input("   Ruta: ").strip().strip('"').strip("'")
        source_path = Path(source)
        if source_path.exists():
            break
        print("   ❌ Ruta no encontrada. Intenta de nuevo.")

    # 2) Formato de salida
    print("\n🎯 ¿A qué formato deseas convertir?")
    print("   1️⃣  WebP  (mejor compresión, recomendado para web)")
    print("   2️⃣  JPG   (reduce peso, sin transparencia)")
    print("   3️⃣  PNG   (con transparencia)")
    while True:
        choice = input("   Elige [1] (Enter = WebP): ").strip() or "1"
        if choice in ("1", "2", "3"):
            output_format = {"1": "WEBP", "2": "JPG", "3": "PNG"}[choice]
            break
        print("   ❌ Opción no válida. Elige 1, 2 o 3.")

    # 3) Remover fondo
    remove_bg = ask_yes_no("\n🎨 ¿Remover el fondo de las imágenes?", default=False)
    if remove_bg:
        print("   ⚠️  Requiere 'rembg'. Si no lo tienes: pip install rembg")

    # 4) Ancho máximo
    while True:
        raw = input("\n📐 Ancho máximo en píxeles [Enter = 1600]: ").strip()
        if raw == "":
            max_width = 1600
            break
        try:
            max_width = int(raw)
            if max_width > 0:
                break
        except ValueError:
            pass
        print("   ❌ Ingresa un número válido mayor a 0.")

    # 5) Calidad
    while True:
        raw = input("🎚️  Calidad 1-100 [Enter = 80]: ").strip()
        if raw == "":
            quality = 80
            break
        try:
            quality = int(raw)
            if 1 <= quality <= 100:
                break
        except ValueError:
            pass
        print("   ❌ Ingresa un número entre 1 y 100.")

    return source_path, output_format, max_width, quality, remove_bg


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Optimize images: reduce weight, convert format, and optionally remove background.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive mode (recommended)
  python optimize_images.py

  # With arguments
  python optimize_images.py --source ./images --format webp --max-width 1600 --quality 80
  python optimize_images.py --source ./photos --format jpg --max-width 1200 --remove-bg
  python optimize_images.py --source ./products --format png --remove-bg --quality 90
        """
    )
    parser.add_argument("--source", help="Source directory with images")
    parser.add_argument("--format", choices=["jpg", "webp", "png"], help="Output format: jpg, webp or png")
    parser.add_argument("--max-width", type=int, default=1600, help="Maximum output width in pixels (default: 1600)")
    parser.add_argument("--quality", type=int, default=80, help="Quality percentage 1-100 (default: 80)")
    parser.add_argument("--remove-bg", action="store_true", help="Remove background from images (requires rembg)")
    parser.add_argument("--extensions", nargs="+", default=[".jpg", ".jpeg", ".png", ".webp"], help="Image extensions to process (default: .jpg .jpeg .png .webp)")
    args = parser.parse_args()

    # Get inputs: from args or interactive mode
    if args.source and args.format:
        source_path = Path(args.source)
        output_format = args.format.upper()
        max_width = args.max_width
        quality = args.quality
        remove_bg = args.remove_bg
        extensions = [ext if ext.startswith('.') else f".{ext}" for ext in args.extensions]
    else:
        source_path, output_format, max_width, quality, remove_bg = get_user_input()
        extensions = [".jpg", ".jpeg", ".png", ".webp"]

    if not source_path.exists():
        raise SystemExit(f"❌ Ruta no encontrada: {source_path}")

    # Accept a single image OR a folder
    entries = collect_entries(source_path, extensions)

    if not entries:
        ext_list = ", ".join(extensions)
        raise SystemExit(f"❌ No se encontraron imágenes ({ext_list}) en {source_path}")

    # Determine output directory and extension
    suffix = ".webp" if output_format == "WEBP" else ".png" if output_format == "PNG" else ".jpg"
    if source_path.is_file():
        # Una sola imagen: la base para rutas relativas es su carpeta
        base_dir = source_path.parent
        output_dir = base_dir / f"{source_path.stem}-optimized"
    else:
        base_dir = source_path
        output_dir = source_path.parent / f"{source_path.name}-optimized"

    total_before = 0
    total_after = 0
    ext_list = ", ".join(extensions)
    tipo = "imagen" if source_path.is_file() else f"{len(entries)} archivos"
    print(f"\n✨ Procesando {tipo}...")
    print(f"   De  : {source_path}")
    print(f"   A   : {output_dir}")
    print(f"   Extensiones: {ext_list}")
    print(f"   Formato: {output_format} | Ancho: {max_width}px | Calidad: {quality}%")
    if remove_bg:
        print(f"   Remover fondo: ✅ Sí")
    print()

    for src_path in entries:
        rel_path = src_path.relative_to(base_dir)
        output_path = output_dir / rel_path.with_suffix(suffix)
        before, after = optimize_image(src_path, output_path, output_format, max_width, quality, remove_bg)
        total_before += before
        total_after += after
        savings_pct = 100 * after / before
        print(f"  ✅ {str(rel_path):<50} {before:>10,} → {after:>10,} ({savings_pct:>5.1f}%)")

    reduction_pct = 100 * (total_before - total_after) / total_before
    print("\n" + "="*80)
    print("📊 RESUMEN:")
    print(f"  Archivos       : {len(entries)}")
    print(f"  Peso original  : {total_before:,} bytes ({total_before/1024/1024:.2f} MB)")
    print(f"  Peso optimizado: {total_after:,} bytes ({total_after/1024/1024:.2f} MB)")
    print(f"  Reducción      : {total_before-total_after:,} bytes ({reduction_pct:.1f}%)")
    print(f"  📂 Carpeta destino: {output_dir}")
    print("="*80)


if __name__ == "__main__":
    main()
