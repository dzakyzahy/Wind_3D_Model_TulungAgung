#!/usr/bin/env python3
"""
download_satelit.py — Pengunduh & Pemotong Otomatis Citra Satelit Tulungagung
Mengunduh citra satelit resolusi tinggi dari Esri World Imagery tepat pada batas koordinat:
Latitude : -9.29 s.d. -7.29
Longitude: 110.80 s.d. 112.80
"""

import os
import sys
import math
import time
import base64
import urllib.request
from PIL import Image

# Force utf-8 stdout if possible, or ascii clean
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Batas Domain ERA5 / DEMNAS Tulungagung
LAT_MIN = -9.29
LAT_MAX = -7.29
LON_MIN = 110.80
LON_MAX = 112.80

# Level Zoom (Z=10 memberikan resolusi sekitar ~1500x1500 px untuk domain 2x2 derajat)
ZOOM = 10

def lon_to_tile_x(lon, z):
    return (lon + 180.0) / 360.0 * (2 ** z)

def lat_to_tile_y(lat, z):
    lat_rad = math.radians(lat)
    return (1.0 - math.log(math.tan(lat_rad) + 1.0 / math.cos(lat_rad)) / math.pi) / 2.0 * (2 ** z)

def download_tile(z, x, y, filepath):
    url = f"https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    })
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                with open(filepath, 'wb') as f:
                    f.write(response.read())
            return True
        except Exception as e:
            time.sleep(1)
    return False

def main():
    print("=" * 60)
    print(" [SATELIT] PENGUNDUH OTOMATIS TEKSTUR SATELIT TULUNGAGUNG")
    print("=" * 60)
    print(f"[INFO] Bounding Box : Lat [{LAT_MIN}, {LAT_MAX}], Lon [{LON_MIN}, {LON_MAX}]")
    print(f"[INFO] Zoom Level   : {ZOOM} (Esri World Imagery)")
    
    # Hitung rentang tile
    x_float_min = lon_to_tile_x(LON_MIN, ZOOM)
    x_float_max = lon_to_tile_x(LON_MAX, ZOOM)
    y_float_top = lat_to_tile_y(LAT_MAX, ZOOM)    # Lat utara -> Y kecil
    y_float_bot = lat_to_tile_y(LAT_MIN, ZOOM)    # Lat selatan -> Y besar
    
    x_min = int(math.floor(x_float_min))
    x_max = int(math.floor(x_float_max))
    y_min = int(math.floor(y_float_top))
    y_max = int(math.floor(y_float_bot))
    
    nx = x_max - x_min + 1
    ny = y_max - y_min + 1
    total_tiles = nx * ny
    print(f"[INFO] Mengunduh grid {nx} x {ny} = {total_tiles} tiles...")
    
    # Buat folder sementara untuk tile
    os.makedirs("temp_tiles", exist_ok=True)
    
    # Unduh semua tile
    count = 0
    for y in range(y_min, y_max + 1):
        for x in range(x_min, x_max + 1):
            count += 1
            tile_path = os.path.join("temp_tiles", f"tile_{ZOOM}_{x}_{y}.jpg")
            print(f"   [{count:2d}/{total_tiles}] Mengunduh tile ({x}, {y})...", end=" ", flush=True)
            if not os.path.exists(tile_path) or os.path.getsize(tile_path) == 0:
                success = download_tile(ZOOM, x, y, tile_path)
                if success:
                    print("OK")
                else:
                    print("GAGAL")
            else:
                print("Sudah ada (Cache)")
                
    print("\n[PROSES] Menggabungkan tiles menjadi kanvas utuh...")
    canvas_w = nx * 256
    canvas_h = ny * 256
    canvas = Image.new('RGB', (canvas_w, canvas_h))
    
    for y in range(y_min, y_max + 1):
        for x in range(x_min, x_max + 1):
            tile_path = os.path.join("temp_tiles", f"tile_{ZOOM}_{x}_{y}.jpg")
            if os.path.exists(tile_path):
                try:
                    img = Image.open(tile_path)
                    px = (x - x_min) * 256
                    py = (y - y_min) * 256
                    canvas.paste(img, (px, py))
                except Exception as e:
                    print(f"[WARN] Peringatan: Tile rusak ({x}, {y})")
                    
    print("[PROSES] Memotong (cropping) sesuai koordinat presisi 100%...")
    crop_left   = int((x_float_min - x_min) * 256)
    crop_right  = int((x_float_max - x_min) * 256)
    crop_top    = int((y_float_top - y_min) * 256)
    crop_bottom = int((y_float_bot - y_min) * 256)
    
    cropped = canvas.crop((crop_left, crop_top, crop_right, crop_bottom))
    
    # Resize ke 2048x2048 (Power of 2 sangat optimal untuk rendering tekstur 3D GPU)
    print("[PROSES] Mengoptimalkan resolusi tekstur ke 2048x2048 (4K UHD)...")
    resample_method = getattr(Image, 'Resampling', Image).LANCZOS
    final_image = cropped.resize((2048, 2048), resample=resample_method)
    
    out_path = "satellite_texture.jpg"
    final_image.save(out_path, "JPEG", quality=95)
    
    print("[PROSES] Membuat satellite_bundle.js (Data URI Base64 untuk bypass CORS file://)...")
    with open(out_path, "rb") as f:
        b64_str = base64.b64encode(f.read()).decode("utf-8")
    bundle_path = "satellite_bundle.js"
    with open(bundle_path, "w", encoding="utf-8") as f:
        f.write(f'window.SATELLITE_TEXTURE_BASE64 = "data:image/jpeg;base64,{b64_str}";\n')
    
    # Bersihkan temp_tiles
    try:
        for f in os.listdir("temp_tiles"):
            os.remove(os.path.join("temp_tiles", f))
        os.rmdir("temp_tiles")
    except Exception:
        pass
        
    print("=" * 60)
    print(f"[SUKSES] Tekstur satelit disimpan di : {os.path.abspath(out_path)}")
    print(f"[SUKSES] Bundle CORS disimpan di     : {os.path.abspath(bundle_path)}")
    print("[INFO] Silakan refresh/reload halaman index.html di browser Anda!")
    print("=" * 60)

if __name__ == "__main__":
    main()
