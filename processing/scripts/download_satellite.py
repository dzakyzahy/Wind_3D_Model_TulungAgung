"""
Download citra satelit untuk visualisasi 3D Tulungagung
Source: ESRI World Imagery (free, no API key needed)
Output: visualization/satellite_texture.jpg (1024x1024 px)

Bounding box domain ERA5:
  Lat: -9.29 (S) hingga -7.29 (N)
  Lon: 110.8 (W) hingga 112.8 (E)
"""

import os
import math
import urllib.request
import time
from PIL import Image
import io

# ── Konfigurasi ────────────────────────────────────────────
OUTPUT_PATH = r"D:\ITB2\Pak_RK\MetOcean_Tulungagung\kode_zahy\WindModel3DProject\visualization\satellite_texture.jpg"
OUTPUT_SIZE  = (2048, 2048)   # ukuran output dalam pixel (2K ultra-sharp)
ZOOM_LEVEL   = 10              # zoom 10 = detail cukup untuk domain 2°×2°
                               # zoom 11 lebih detail tapi lebih banyak tile

# Bounding box domain — SAMA PERSIS dengan domain ERA5 di index.html
LAT_MIN = -9.29   # Selatan
LAT_MAX = -7.29   # Utara
LON_MIN = 110.8   # Barat
LON_MAX = 112.8   # Timur

# ESRI World Imagery tile URL (tidak butuh API key)
# Alternatif jika ESRI down: gunakan Google Hybrid
TILE_URL = "https://services.arcgisonline.com/arcgis/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
# Backup: TILE_URL = "https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}"

TILE_SIZE = 256  # pixel per tile (standard)

# ── Konversi koordinat ──────────────────────────────────────
def lat_lon_to_tile(lat, lon, zoom):
    """Konversi lat/lon WGS84 ke tile x,y pada zoom level tertentu."""
    lat_rad = math.radians(lat)
    n = 2 ** zoom
    x = int((lon + 180.0) / 360.0 * n)
    y = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return x, y

def tile_to_lat_lon(x, y, zoom):
    """Konversi tile x,y ke koordinat sudut kiri-atas (lat, lon)."""
    n = 2 ** zoom
    lon = x / n * 360.0 - 180.0
    lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * y / n)))
    lat = math.degrees(lat_rad)
    return lat, lon

# ── Download tile ───────────────────────────────────────────
def download_tile(x, y, z, url_template, retries=3):
    url = url_template.replace('{x}', str(x)).replace('{y}', str(y)).replace('{z}', str(z))
    headers = {'User-Agent': 'Mozilla/5.0 (compatible; academic research)'}
    req = urllib.request.Request(url, headers=headers)
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return Image.open(io.BytesIO(resp.read())).convert('RGB')
        except Exception as e:
            print(f"  Retry {attempt+1}/{retries} untuk tile {x},{y}: {e}")
            time.sleep(1 + attempt)
    return None

# ── Main ────────────────────────────────────────────────────
def main():
    print(f"Domain: Lat [{LAT_MIN}, {LAT_MAX}], Lon [{LON_MIN}, {LON_MAX}]")
    print(f"Zoom level: {ZOOM_LEVEL}")

    # Hitung range tile yang dibutuhkan
    # Ingat: y tile bertambah ke BAWAH (selatan), jadi lat_min = y_max
    x_min, y_min = lat_lon_to_tile(LAT_MAX, LON_MIN, ZOOM_LEVEL)  # sudut kiri atas
    x_max, y_max = lat_lon_to_tile(LAT_MIN, LON_MAX, ZOOM_LEVEL)  # sudut kanan bawah
    
    nx_tiles = x_max - x_min + 1
    ny_tiles = y_max - y_min + 1
    total_tiles = nx_tiles * ny_tiles
    
    print(f"Tile range: x=[{x_min},{x_max}], y=[{y_min},{y_max}]")
    print(f"Jumlah tile: {nx_tiles}×{ny_tiles} = {total_tiles} tiles")

    # Buat canvas kosong untuk mosaic semua tile
    canvas_w = nx_tiles * TILE_SIZE
    canvas_h = ny_tiles * TILE_SIZE
    canvas = Image.new('RGB', (canvas_w, canvas_h), (0, 0, 0))
    
    # Download dan paste setiap tile
    n_downloaded = 0
    for ty in range(y_min, y_max + 1):
        for tx in range(x_min, x_max + 1):
            px = (tx - x_min) * TILE_SIZE
            py = (ty - y_min) * TILE_SIZE
            print(f"  Downloading tile {tx},{ty} ({n_downloaded+1}/{total_tiles})...")
            img = download_tile(tx, ty, ZOOM_LEVEL, TILE_URL)
            if img:
                canvas.paste(img, (px, py))
                n_downloaded += 1
            else:
                print(f"  GAGAL tile {tx},{ty} — skip")
            time.sleep(0.1)  # rate limiting yang sopan
    
    print(f"\nDownloaded {n_downloaded}/{total_tiles} tiles")
    
    # ── KRITIS: Reprojection eksak Web Mercator (EPSG:3857) -> WGS84 Equirectangular (EPSG:4326) ──
    # Mengatasi ketidakcocokan proyeksi (distorsi logaritmik vertikal) dan forced aspect ratio!
    import numpy as np
    from scipy.ndimage import map_coordinates

    print("\n[Reprojection] Memulai transformasi spasial Web Mercator -> WGS84 Equirectangular...")
    canvas_arr = np.array(canvas)
    out_w, out_h = OUTPUT_SIZE

    # 1. Buat grid target WGS84 linier (sama persis dengan grid DEMNAS & ERA5 di 3D model)
    lats = np.linspace(LAT_MAX, LAT_MIN, out_h)  # Utara ke Selatan
    lons = np.linspace(LON_MIN, LON_MAX, out_w)  # Barat ke Timur
    lons_grid, lats_grid = np.meshgrid(lons, lats)

    # 2. Konversi koordinat WGS84 (lat/lon) ke koordinat tile Web Mercator (float)
    lats_rad = np.radians(lats_grid)
    n = 2.0 ** ZOOM_LEVEL
    x_tile_float = (lons_grid + 180.0) / 360.0 * n
    y_tile_float = (1.0 - np.arcsinh(np.tan(lats_rad)) / np.pi) / 2.0 * n

    # 3. Konversi koordinat tile ke koordinat piksel pada canvas mosaic (origin: x_min, y_min)
    x_canvas = (x_tile_float - x_min) * TILE_SIZE
    y_canvas = (y_tile_float - y_min) * TILE_SIZE

    # 4. Interpolasi warna R, G, B dari canvas Web Mercator ke grid WGS84
    print(f"  Interpolasi {out_w}×{out_h} piksel (Bicubic order=3)...")
    coords = np.stack([y_canvas, x_canvas])
    out_r = map_coordinates(canvas_arr[:, :, 0], coords, order=3, mode='nearest')
    out_g = map_coordinates(canvas_arr[:, :, 1], coords, order=3, mode='nearest')
    out_b = map_coordinates(canvas_arr[:, :, 2], coords, order=3, mode='nearest')

    out_arr = np.stack([out_r, out_g, out_b], axis=-1).astype(np.uint8)
    result = Image.fromarray(out_arr)

    # Simpan
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    result.save(OUTPUT_PATH, 'JPEG', quality=92)
    print(f"\nSaved: {OUTPUT_PATH}")
    print(f"Size: {result.size}")

    # ── Buat metadata JSON untuk verifikasi di browser ──
    import json
    meta = {
        "bbox": {
            "lat_min": LAT_MIN, "lat_max": LAT_MAX,
            "lon_min": LON_MIN, "lon_max": LON_MAX
        },
        "zoom": ZOOM_LEVEL,
        "tiles_downloaded": n_downloaded,
        "output_size": OUTPUT_SIZE,
        "projection": "WGS84 Equirectangular (EPSG:4326) reprojected from Web Mercator (EPSG:3857)",
        "note": "UV in Three.js: u=(x/TS)+0.5, v=1-((z/TS)+0.5), no flip needed"
    }
    meta_path = OUTPUT_PATH.replace('.jpg', '_meta.json')
    with open(meta_path, 'w') as f:
        json.dump(meta, f, indent=2)
    print(f"Metadata: {meta_path}")

if __name__ == '__main__':
    main()
