"""
SRG Security - Auditor y descargador de imágenes faltantes
Revisa qué imágenes de productos faltan en /images/ y genera un reporte.
Intenta descargar las faltantes buscando en la web.
"""
import os
import re
import json
import urllib.request
import urllib.parse
import ssl
import time

# Ruta base del proyecto
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGES_DIR = os.path.join(BASE_DIR, "images")
INDEX_FILE = os.path.join(BASE_DIR, "index.html")
REPORT_FILE = os.path.join(BASE_DIR, "imagenes_faltantes.txt")

# Ignorar SSL para descargas
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


def extract_products_from_html(html_path):
    """Extrae todos los productos del JS embebido en index.html"""
    with open(html_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Extraer el imageFileMap
    map_match = re.search(r"const imageFileMap\s*=\s*\{([^}]+)\}", content, re.DOTALL)
    image_file_map = {}
    if map_match:
        map_text = map_match.group(1)
        pairs = re.findall(r"'([^']+)'\s*:\s*'([^']+)'", map_text)
        for key, val in pairs:
            image_file_map[key] = val

    # Extraer productos: { name: "...", price: ..., image: "..." }
    products = []
    pattern = r'\{\s*name:\s*"([^"]+)"\s*,\s*price:\s*([0-9.]+)\s*,\s*image:\s*"([^"]+)"\s*\}'
    matches = re.findall(pattern, content)
    for name, price, image_key in matches:
        real_file = image_file_map.get(image_key, image_key)
        products.append({
            "name": name,
            "price": price,
            "image_key": image_key,
            "expected_file": real_file
        })
    return products


def check_image_exists(expected_file):
    """Revisa si la imagen existe como .jpg o .png"""
    for ext in [".jpg", ".png", ".jpeg", ".webp"]:
        path = os.path.join(IMAGES_DIR, expected_file + ext)
        if os.path.exists(path):
            return path
    return None


def try_download_image(product_name, save_name):
    """Intenta descargar una imagen buscando en DuckDuckGo"""
    query = f"{product_name} cámara seguridad producto"
    search_url = f"https://duckduckgo.com/?q={urllib.parse.quote(query)}&iax=images&ia=images"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    # Intentar buscar via la API lite de DuckDuckGo
    api_url = f"https://api.duckduckgo.com/?q={urllib.parse.quote(product_name)}&format=json&no_redirect=1"
    try:
        req = urllib.request.Request(api_url, headers=headers)
        with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            image_url = data.get("Image", "")
            if image_url and image_url.startswith("http"):
                save_path = os.path.join(IMAGES_DIR, save_name + ".jpg")
                urllib.request.urlretrieve(image_url, save_path)
                return True, save_path
    except Exception:
        pass

    return False, None


def main():
    print("=" * 60)
    print("  SRG Security - Auditor de Imágenes")
    print("=" * 60)

    if not os.path.exists(INDEX_FILE):
        print(f"ERROR: No se encontró {INDEX_FILE}")
        return

    products = extract_products_from_html(INDEX_FILE)
    print(f"\nProductos encontrados en index.html: {len(products)}")

    found = []
    missing = []
    downloaded = []

    for p in products:
        path = check_image_exists(p["expected_file"])
        if path:
            found.append(p)
        else:
            missing.append(p)

    print(f"  ✅ Con imagen:  {len(found)}")
    print(f"  ❌ Sin imagen:  {len(missing)}")

    if missing:
        print(f"\n{'─' * 60}")
        print("Intentando descargar imágenes faltantes...")
        print(f"{'─' * 60}")

        for i, p in enumerate(missing):
            print(f"\n  [{i+1}/{len(missing)}] {p['name']}")
            print(f"    Archivo esperado: images/{p['expected_file']}.jpg")

            ok, path = try_download_image(p["name"], p["expected_file"])
            if ok:
                print(f"    ✅ Descargada → {path}")
                downloaded.append(p)
            else:
                print(f"    ⚠️  No se pudo descargar automáticamente")

            time.sleep(0.5)  # No saturar

    # Recalcular faltantes después de descargas
    still_missing = []
    for p in missing:
        if p not in downloaded:
            still_missing.append(p)

    # Generar reporte TXT
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write("=" * 70 + "\n")
        f.write("  REPORTE DE IMÁGENES - SRG Security\n")
        f.write(f"  Fecha: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 70 + "\n\n")

        f.write(f"Total de productos: {len(products)}\n")
        f.write(f"Con imagen existente: {len(found)}\n")
        f.write(f"Descargadas ahora: {len(downloaded)}\n")
        f.write(f"Todavía faltantes: {len(still_missing)}\n\n")

        if still_missing:
            f.write("─" * 70 + "\n")
            f.write("  IMÁGENES FALTANTES - Debes agregar manualmente:\n")
            f.write("─" * 70 + "\n\n")
            f.write(f"{'Producto':<50} {'Archivo necesario'}\n")
            f.write(f"{'─'*50} {'─'*30}\n")
            for p in still_missing:
                f.write(f"{p['name']:<50} images/{p['expected_file']}.jpg\n")

        f.write("\n\n")
        f.write("─" * 70 + "\n")
        f.write("  TODAS LAS IMÁGENES ENCONTRADAS:\n")
        f.write("─" * 70 + "\n\n")
        for p in found + downloaded:
            path = check_image_exists(p["expected_file"])
            f.write(f"  ✅ {p['name']:<45} → {os.path.basename(path) if path else '?'}\n")

    print(f"\n{'=' * 60}")
    print(f"  RESUMEN FINAL")
    print(f"{'=' * 60}")
    print(f"  Encontradas:     {len(found)}")
    print(f"  Descargadas:     {len(downloaded)}")
    print(f"  Aún faltantes:   {len(still_missing)}")
    print(f"\n  📄 Reporte guardado en: {REPORT_FILE}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
