"""
Ekstraksi data vektor Rupa Bumi Indonesia (RBI 25K) dari Esri File Geodatabase (.gdb) di dalam file ZIP.
Melakukan clipping ketat pada domain Tulungagung: Lat [-9.29, -7.29], Lon [110.8, 112.8].
Menyimpan hasil ekstraksi Jalan Raya, Sungai, dan Batas Administrasi ke dalam rbi_bundle.js.
"""
import os, glob, json
import numpy as np
import geopandas as gpd
from shapely.geometry import box, LineString, MultiLineString

# ── Konfigurasi ─────────────────────────────────────────────────────────────
BASE_DIR  = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RBI_DIR   = os.path.join(BASE_DIR, 'Data', 'RBI')
OUT_JS    = os.path.join(BASE_DIR, 'visualization', 'rbi_bundle.js')

# Bounding box domain persis sama dengan ERA5 & DEMNAS
LON_MIN, LON_MAX = 110.8, 112.8
LAT_MIN, LAT_MAX = -9.29, -7.29
BBOX_POLYGON = box(LON_MIN, LAT_MIN, LON_MAX, LAT_MAX)

def extract_layer_from_zip(zip_path, layer_name):
    """Membaca layer dari .gdb di dalam file zip RBI, clip ke bbox, simplify"""
    try:
        # Cari nama geodatabase di dalam zip
        import zipfile
        with zipfile.ZipFile(zip_path) as z:
            gdbs = list(set([f.split('/')[0] for f in z.namelist() if '.gdb' in f]))
        if not gdbs:
            return []
        gdb_name = gdbs[0]
        uri = f"zip://{zip_path}!{gdb_name}"
        
        # Baca layer dengan pyogrio/geopandas (hanya bbox yang bersinggungan)
        gdf = gpd.read_file(uri, layer=layer_name, bbox=(LON_MIN, LAT_MIN, LON_MAX, LAT_MAX))
        if gdf.empty:
            return []
        
        # Filter cerdas untuk Jalan Raya: jalan utama, jalan bermakna/bernama, atau jalan lokal panjang
        if layer_name == 'JALAN_LN_25K':
            named = (gdf['NAMOBJ'].str.strip() != '') & (gdf['NAMOBJ'].str.strip() != 'None') & gdf['NAMOBJ'].notna() if 'NAMOBJ' in gdf.columns else False
            main = gdf['REMARK'].str.contains('Arteri|Kolektor|Raya|Utama|Provinsi|Negara|Tol', case=False, na=False) if 'REMARK' in gdf.columns else True
            long_lokal = (gdf['REMARK'].str.contains('Lokal', case=False, na=False)) & (gdf.geometry.length > 0.01) if 'REMARK' in gdf.columns else False
            gdf = gdf[main | named | long_lokal]
            
        # Filter cerdas untuk Sungai: sungai utama, sungai bernamna, atau alur panjang (>1.5 km)
        elif layer_name == 'SUNGAI_LN_25K':
            named = (gdf['NAMOBJ'].str.strip() != '') & (gdf['NAMOBJ'].str.strip() != 'None') & gdf['NAMOBJ'].notna() if 'NAMOBJ' in gdf.columns else False
            main = gdf['REMARK'].str.contains('Sungai$|Dua Garis|Utama|Besar', case=False, na=False) & ~gdf['REMARK'].str.contains('Alur|Satu', case=False, na=False) if 'REMARK' in gdf.columns else True
            long_stream = gdf.geometry.length > 0.015
            gdf = gdf[named | main | long_stream]
                
        # Clip ketat ke BBOX_POLYGON
        gdf_clipped = gpd.clip(gdf, BBOX_POLYGON)
        
        # Simplify geometry untuk rendering cepat di WebGL (0.0003 deg ~ 30 meter)
        gdf_clipped['geometry'] = gdf_clipped['geometry'].simplify(0.0003, preserve_topology=True)
        
        # Ekstrak koordinat garis
        lines = []
        for geom in gdf_clipped['geometry']:
            if geom is None or geom.is_empty:
                continue
            if isinstance(geom, LineString):
                coords = [[round(p[0], 5), round(p[1], 5)] for p in geom.coords]
                if len(coords) >= 2:
                    lines.append(coords)
            elif isinstance(geom, MultiLineString):
                for line in geom.geoms:
                    coords = [[round(p[0], 5), round(p[1], 5)] for p in line.coords]
                    if len(coords) >= 2:
                        lines.append(coords)
        return lines
    except Exception as e:
        # Layer mungkin tidak ada di gdb tertentu
        return []

def main():
    print("=" * 65)
    print("  EKSTRAKSI & BUNDLING DATA RUPA BUMI INDONESIA (RBI 25K)")
    print("=" * 65)
    
    zip_files = glob.glob(os.path.join(RBI_DIR, "*.zip"))
    print(f"[INFO] Ditemukan {len(zip_files)} file ZIP RBI di {RBI_DIR}")
    
    rbi_data = {
        "roads": [],
        "rivers": [],
        "admin": []
    }
    
    for z in sorted(zip_files):
        name = os.path.basename(z)
        print(f"\n[Processing] {name}...")
        
        # 1. Jalan Raya
        roads = extract_layer_from_zip(z, 'JALAN_LN_25K')
        rbi_data["roads"].extend(roads)
        print(f"  -> Roads: +{len(roads)} garis")
        
        # 2. Sungai
        rivers = extract_layer_from_zip(z, 'SUNGAI_LN_25K')
        rbi_data["rivers"].extend(rivers)
        print(f"  -> Rivers: +{len(rivers)} garis")
        
        # 3. Batas Administrasi
        admin = extract_layer_from_zip(z, 'ADMINISTRASI_LN_KABKOTA')
        rbi_data["admin"].extend(admin)
        print(f"  -> Admin: +{len(admin)} garis")
        
    print("\n" + "=" * 65)
    print(f"[SUMMARY] Total garis terektraksi di domain Tulungagung:")
    print(f"  - Jalan Raya  : {len(rbi_data['roads'])} polylines")
    print(f"  - Sungai      : {len(rbi_data['rivers'])} polylines")
    print(f"  - Batas Admin : {len(rbi_data['admin'])} polylines")
    
    # Simpan ke rbi_bundle.js
    json_str = json.dumps(rbi_data, separators=(',', ':'))
    js_content = f"""// Auto-generated by make_rbi_overlay.py
// Rupa Bumi Indonesia (RBI 25K) | Domain: Lat [-9.29, -7.29], Lon [110.8, 112.8]
window.RBI_DATA = {json_str};
console.log('[RBI] Vektor GIS ter-bundle:',
  'Roads:', window.RBI_DATA.roads.length,
  'Rivers:', window.RBI_DATA.rivers.length,
  'Admin:', window.RBI_DATA.admin.length
);
"""
    os.makedirs(os.path.dirname(OUT_JS), exist_ok=True)
    with open(OUT_JS, 'w', encoding='utf-8') as f:
        f.write(js_content)
        
    size_mb = os.path.getsize(OUT_JS) / (1024 * 1024)
    print(f"\n[DONE] Saved bundle: {OUT_JS} ({size_mb:.2f} MB)")
    if size_mb > 5.0:
        print("[WARN] Ukuran bundle > 5MB, pertimbangkan simplifikasi lebih agresif.")

if __name__ == '__main__':
    main()
