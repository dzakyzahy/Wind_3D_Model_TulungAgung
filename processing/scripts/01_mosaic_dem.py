"""
01_mosaic_dem.py — Modul 1: Preprocessing DEM DEMNAS
=====================================================
Input : cfg.DIR_DEMNAS\\DEMNAS_*.tif  (12 tile)
Output: cfg.DIR_DEM_PROC\\dem_8m_clipped.tif
        cfg.DIR_DEM_PROC\\dem_90m.tif
        cfg.DIR_DEM_PROC\\dem_270m.tif
        cfg.DIR_PROC\\terrain_grid.json
        cfg.DIR_PROC\\terrain_stats.json
        cfg.DIR_OUTPUT\\dem_mosaic_preview.png
"""
import sys, os, time, glob, json, warnings
warnings.filterwarnings("ignore")
t0 = time.time()

sys.path.insert(0, r"D:\ITB2\Pak_RK\MetOcean_Tulungagung\kode_zahy\WindModel3DProject")
import config as cfg

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

files_ok = []
files_fail = []

# ══════════════════════════════════════════════════════════════════════════════
print("[INFO] Modul 1 — DEM Preprocessing")
print(f"[INFO] DEMNAS dir: {cfg.DIR_DEMNAS}")

# ── 1A. Scan DEMNAS tiles ─────────────────────────────────────────────────────
tif_files = sorted(glob.glob(os.path.join(cfg.DIR_DEMNAS, "DEMNAS_*.tif")))
USE_DEMO  = len(tif_files) == 0

if USE_DEMO:
    print("[WARN] Tidak ada DEMNAS_*.tif — menggunakan DEM sintetis (demo mode)")
else:
    print(f"[INFO] Ditemukan {len(tif_files)} tile DEMNAS")

# ── Helper: Hasilkan DEM sintetis realistis untuk Tulungagung ────────────────
def make_synthetic_dem(nx=150, ny=150):
    """Generate realistic synthetic DEM for Tulungagung region."""
    x = np.linspace(-1, 1, nx)
    y = np.linspace(-1, 1, ny)
    X, Y = np.meshgrid(x, y)

    # Gunung Wilis (N-W quadrant, ~2552m)
    wilis = 2500 * np.exp(-((X + 0.45)**2 + (Y - 0.55)**2) / 0.18)
    # Gunung Kelud / perbukitan SE (~1731m)
    kelud = 1600 * np.exp(-((X - 0.60)**2 + (Y + 0.40)**2) / 0.15)
    # Dataran Tulungagung (tengah-S)
    plain = 80 * np.exp(-((X + 0.1)**2 + (Y + 0.15)**2) / 0.25)
    # Pantai selatan (S edge) ~0–20m
    coast = np.clip(30 * (1 + Y), 0, 50) * (Y > 0.6)
    # Background noise
    noise = 15 * (np.sin(X * 5) * np.cos(Y * 4) + 0.3 * np.random.randn(ny, nx))

    dem = np.clip(wilis + kelud + plain + coast + noise, 0, 3000)
    return dem.astype(np.float32)

# ── 1B–1D. Mosaik dan proses DEM ─────────────────────────────────────────────
if not USE_DEMO:
    try:
        import rasterio
        from rasterio.merge import merge
        from rasterio.warp import calculate_default_transform, reproject, Resampling
        from rasterio.transform import from_bounds
        from scipy.ndimage import generic_filter

        # Buka semua tile
        src_files = [rasterio.open(f) for f in tif_files]
        print(f"[INFO] Mosaik {len(src_files)} tiles dengan bounds domain...")
        mosaic_arr, mosaic_transform = merge(src_files, bounds=(cfg.LON_MIN, cfg.LAT_MIN, cfg.LON_MAX, cfg.LAT_MAX))
        mosaic_crs = src_files[0].crs
        for s in src_files:
            s.close()

        # Ambil band pertama
        dem_arr = mosaic_arr[0].astype(np.float32)

        # Fill NoData
        nodata_val = -9999.0
        mask_nodata = dem_arr < -1000
        dem_arr[mask_nodata] = np.nan
        print("[INFO] Fill NoData dengan median filter 3×3...")
        def fill_median(a):
            center = a[len(a)//2]
            if np.isnan(center):
                valid = a[~np.isnan(a)]
                return np.median(valid) if len(valid) > 0 else 0.0
            return center
        dem_arr = generic_filter(dem_arr, fill_median, size=3, mode='nearest')
        dem_arr = np.nan_to_num(dem_arr, nan=0.0)

        # Reproject ke WGS84 (sudah seharusnya, tapi pastikan)
        dst_crs = "EPSG:4326"

        # Clip ke domain
        from rasterio.crs import CRS
        from rasterio.transform import from_bounds as tf_from_bounds
        import rasterio.transform

        # Buat grid kecil → resample ke 150×150 untuk terrain_grid
        print("[DONE] Modul 1.B — Mosaik DEM selesai")
        dem_data = dem_arr
        USE_RASTERIO = True

    except Exception as e:
        print(f"[WARN] rasterio gagal: {e} — pakai DEM sintetis")
        USE_DEMO = True
        USE_RASTERIO = False

if USE_DEMO:
    print("[INFO] Membuat DEM sintetis 150×150...")
    dem_data = make_synthetic_dem(150, 150)
    USE_RASTERIO = False

# ── Subsample dem_data ke 150×150 ────────────────────────────────────────────
from scipy.ndimage import zoom as sp_zoom

def resample_dem(arr, target_ny, target_nx):
    sy = target_ny / arr.shape[0]
    sx = target_nx / arr.shape[1]
    if abs(sy - 1.0) < 0.01 and abs(sx - 1.0) < 0.01:
        return arr
    return sp_zoom(arr, (sy, sx), order=1).astype(np.float32)

NX, NY = 150, 150
dem_150 = resample_dem(dem_data, NY, NX)
dem_150 = np.clip(dem_150, 0, 4000).astype(np.float32)
print(f"[INFO] DEM 150×150 — min={dem_150.min():.1f}m max={dem_150.max():.1f}m mean={dem_150.mean():.1f}m")

# ── 1E–1F. Simpan TIF (jika rasterio tersedia) ───────────────────────────────
if USE_RASTERIO:
    try:
        from rasterio.transform import from_bounds
        transform_8m = from_bounds(cfg.LON_MIN, cfg.LAT_MIN, cfg.LON_MAX, cfg.LAT_MAX,
                                   dem_data.shape[1], dem_data.shape[0])

        out_8m = os.path.join(cfg.DIR_DEM_PROC, "dem_8m_clipped.tif")
        with rasterio.open(out_8m, 'w', driver='GTiff', height=dem_data.shape[0],
                           width=dem_data.shape[1], count=1, dtype='float32',
                           crs='EPSG:4326', transform=transform_8m) as dst:
            dst.write(dem_data[np.newaxis, ...])
        files_ok.append(out_8m)
        print(f"[DONE] Modul 1.F — dem_8m_clipped.tif tersimpan")

        # 90m dan 270m
        for res_m, label in [(90, "90m"), (270, "270m")]:
            # Perkiraan jumlah pixel
            deg_per_m = 1 / 111000
            ny_out = max(10, int((cfg.LAT_MAX - cfg.LAT_MIN) / (res_m * deg_per_m)))
            nx_out = max(10, int((cfg.LON_MAX - cfg.LON_MIN) / (res_m * deg_per_m)))
            dem_res = resample_dem(dem_data, ny_out, nx_out)
            trf_res = from_bounds(cfg.LON_MIN, cfg.LAT_MIN, cfg.LON_MAX, cfg.LAT_MAX,
                                  nx_out, ny_out)
            out_res = os.path.join(cfg.DIR_DEM_PROC, f"dem_{label}.tif")
            with rasterio.open(out_res, 'w', driver='GTiff',
                               height=ny_out, width=nx_out, count=1,
                               dtype='float32', crs='EPSG:4326', transform=trf_res) as dst:
                dst.write(dem_res[np.newaxis, ...])
            files_ok.append(out_res)
            print(f"[DONE] Modul 1.G — dem_{label}.tif tersimpan ({nx_out}×{ny_out})")
    except Exception as e:
        print(f"[WARN] Simpan TIF gagal: {e}")
        files_fail.append("dem_*.tif")
else:
    print("[WARN] rasterio tidak tersedia — melewati penyimpanan TIF")

# ── 1H. Export terrain_grid.json ─────────────────────────────────────────────
print("[INFO] Membuat terrain_grid.json...")
# Normalisasi ke [0,1] untuk JSON (web visualization menggunakan nilai ternormalisasi)
dem_min = float(dem_150.min())
dem_max = float(dem_150.max())

# Normalisasi untuk visualisasi
if dem_max > dem_min:
    dem_norm = ((dem_150 - dem_min) / (dem_max - dem_min)).astype(np.float32)
else:
    dem_norm = np.zeros_like(dem_150)

terrain_grid = {
    "nx": int(NX),
    "nz": int(NY),
    "lat_min": cfg.LAT_MIN,
    "lat_max": cfg.LAT_MAX,
    "lon_min": cfg.LON_MIN,
    "lon_max": cfg.LON_MAX,
    "elevation_min": round(dem_min, 2),
    "elevation_max": round(dem_max, 2),
    "elevation_mean": round(float(dem_150.mean()), 2),
    "elevation": dem_150.tolist(),         # nilai asli meter
    "elevation_norm": dem_norm.tolist(),   # ternormalisasi 0–1
    "is_demo": USE_DEMO,
}

out_tgrid = os.path.join(cfg.DIR_PROC, "terrain_grid.json")
with open(out_tgrid, "w") as f:
    json.dump(terrain_grid, f, separators=(",", ":"))
files_ok.append(out_tgrid)
print(f"[DONE] Modul 1.H — terrain_grid.json tersimpan ({os.path.getsize(out_tgrid)/1024:.1f} KB)")

# ── 1I. Hitung terrain_stats.json ─────────────────────────────────────────────
print("[INFO] Menghitung terrain_stats.json...")

# Gradien magnitude (ridge detection)
grad_y, grad_x = np.gradient(dem_150.astype(float))
grad_mag = np.sqrt(grad_x**2 + grad_y**2)

# Luas per elevasi band
cell_km2 = ((cfg.LON_MAX - cfg.LON_MIN) * 111 * (cfg.LAT_MAX - cfg.LAT_MIN) * 111) / (NX * NY)

def area_above(dem, threshold):
    return float((dem > threshold).sum() * cell_km2)

# Koordinat puncak tertinggi
peak_idx = np.unravel_index(dem_150.argmax(), dem_150.shape)
peak_lat = cfg.LAT_MAX - (peak_idx[0] / NY) * (cfg.LAT_MAX - cfg.LAT_MIN)
peak_lon = cfg.LON_MIN + (peak_idx[1] / NX) * (cfg.LON_MAX - cfg.LON_MIN)

# Ridge coords: top-20% gradient magnitude → subset
ridge_threshold = np.percentile(grad_mag, 80)
ridge_mask = grad_mag > ridge_threshold
ridge_rows, ridge_cols = np.where(ridge_mask)
# Sample setiap 5 piksel agar tidak terlalu besar
step = max(1, len(ridge_rows) // 200)
ridge_coords = [
    [round(cfg.LAT_MAX - (r / NY) * (cfg.LAT_MAX - cfg.LAT_MIN), 4),
     round(cfg.LON_MIN + (c / NX) * (cfg.LON_MAX - cfg.LON_MIN), 4)]
    for r, c in zip(ridge_rows[::step], ridge_cols[::step])
]

terrain_stats = {
    "elevation_min_m"  : round(dem_min, 2),
    "elevation_max_m"  : round(dem_max, 2),
    "elevation_mean_m" : round(float(dem_150.mean()), 2),
    "elevation_std_m"  : round(float(dem_150.std()), 2),
    "area_total_km2"   : round(cell_km2 * NX * NY, 1),
    "area_above_250m"  : round(area_above(dem_150, 250), 1),
    "area_above_500m"  : round(area_above(dem_150, 500), 1),
    "area_above_1000m" : round(area_above(dem_150, 1000), 1),
    "area_above_1500m" : round(area_above(dem_150, 1500), 1),
    "peak_elevation_m" : round(dem_max, 1),
    "peak_lat"         : round(peak_lat, 4),
    "peak_lon"         : round(peak_lon, 4),
    "gradient_mag_mean": round(float(grad_mag.mean()), 4),
    "gradient_mag_max" : round(float(grad_mag.max()), 4),
    "ridge_coords"     : ridge_coords[:100],   # max 100 titik
    "cell_area_km2"    : round(cell_km2, 4),
    "is_demo"          : USE_DEMO,
}

out_tstats = os.path.join(cfg.DIR_PROC, "terrain_stats.json")
with open(out_tstats, "w") as f:
    json.dump(terrain_stats, f, indent=2)
files_ok.append(out_tstats)
print(f"[DONE] Modul 1.I — terrain_stats.json tersimpan")
print(f"         Area >250m: {terrain_stats['area_above_250m']} km²")
print(f"         Area >500m: {terrain_stats['area_above_500m']} km²")
print(f"         Puncak    : {dem_max:.0f}m @ ({peak_lat:.3f},{peak_lon:.3f})")

# ── 1J. Plot Hillshade + Kontur + Niyama Beach ───────────────────────────────
print("[INFO] Membuat dem_mosaic_preview.png...")

fig, ax = plt.subplots(figsize=(12, 10), facecolor="#0a0e1a")
ax.set_facecolor("#0a0e1a")

# Hillshade
ls = mcolors.LightSource(azdeg=315, altdeg=45)
hillshade = ls.hillshade(dem_150, vert_exag=3, dx=1, dy=1)

# Custom colormap untuk terrain Jawa
from matplotlib.colors import LinearSegmentedColormap
terrain_colors = [
    (0.00, "#1a3a5c"),   # laut/pantai
    (0.05, "#2d5a1b"),   # dataran rendah
    (0.20, "#4a7c2f"),   # perbukitan
    (0.45, "#8b6914"),   # lereng
    (0.70, "#a08030"),   # lereng atas
    (0.90, "#c0a060"),   # batu
    (1.00, "#d4d4d4"),   # puncak
]
cmap_terrain = LinearSegmentedColormap.from_list(
    "tulungagung_terrain",
    [(v, c) for v, c in terrain_colors]
)

extent = [cfg.LON_MIN, cfg.LON_MAX, cfg.LAT_MIN, cfg.LAT_MAX]
img_rgb = ls.shade(dem_150, cmap=cmap_terrain, vert_exag=3, blend_mode="soft",
                   vmin=0, vmax=dem_max)
ax.imshow(img_rgb, extent=extent, origin="upper", aspect="auto")

# Kontur 250m interval
lats = np.linspace(cfg.LAT_MAX, cfg.LAT_MIN, NY)
lons = np.linspace(cfg.LON_MIN, cfg.LON_MAX, NX)
LON_G, LAT_G = np.meshgrid(lons, lats)
levels = np.arange(250, min(dem_max, 3000), 250)
cs = ax.contour(LON_G, LAT_G, dem_150, levels=levels,
                colors="white", linewidths=0.4, alpha=0.35)
ax.clabel(cs, fmt="%dm", fontsize=7, colors="white")

# Titik Niyama Beach
ax.plot(cfg.SITE_LON, cfg.SITE_LAT, "v", color="#ff6b35", markersize=12,
        markeredgecolor="white", markeredgewidth=1.5, zorder=10)
ax.annotate("Niyama Beach\n(Titik Kajian)",
            xy=(cfg.SITE_LON, cfg.SITE_LAT),
            xytext=(cfg.SITE_LON + 0.15, cfg.SITE_LAT - 0.15),
            fontsize=9, color="#ff6b35",
            arrowprops=dict(arrowstyle="->", color="#ff6b35", lw=1.5),
            fontweight="bold")

# Puncak tertinggi
ax.plot(peak_lon, peak_lat, "^", color="#ffd700", markersize=10,
        markeredgecolor="white", markeredgewidth=1, zorder=10)
ax.annotate(f"Puncak {dem_max:.0f}m",
            xy=(peak_lon, peak_lat),
            xytext=(peak_lon - 0.3, peak_lat + 0.1),
            fontsize=8, color="#ffd700",
            arrowprops=dict(arrowstyle="->", color="#ffd700", lw=1.2))

# Domain bounding box
from matplotlib.patches import Rectangle
rect = Rectangle((cfg.LON_MIN, cfg.LAT_MIN),
                 cfg.LON_MAX - cfg.LON_MIN, cfg.LAT_MAX - cfg.LAT_MIN,
                 fill=False, edgecolor="#22d3ee", linewidth=2, linestyle="--")
ax.add_patch(rect)

# Colorbar
sm = plt.cm.ScalarMappable(cmap=cmap_terrain,
                            norm=plt.Normalize(vmin=0, vmax=dem_max))
sm.set_array([])
cbar = plt.colorbar(sm, ax=ax, fraction=0.03, pad=0.02)
cbar.set_label("Elevasi (m)", color="white", fontsize=10)
cbar.ax.yaxis.set_tick_params(color="white")
plt.setp(cbar.ax.yaxis.get_ticklabels(), color="white", fontsize=8)
cbar.outline.set_edgecolor("white")

# Labels
ax.set_xlabel("Bujur (°E)", color="white", fontsize=11)
ax.set_ylabel("Lintang (°S)", color="white", fontsize=11)
ax.tick_params(colors="white", labelsize=9)
for spine in ax.spines.values():
    spine.set_edgecolor("white")

demo_note = " [DEMO DATA]" if USE_DEMO else ""
ax.set_title(f"DEM Topografi Tulungagung — DEMNAS 8m{demo_note}\n"
             f"Domain: {cfg.LAT_MIN}°–{cfg.LAT_MAX}°S | {cfg.LON_MIN}°–{cfg.LON_MAX}°E | "
             f"Resolusi Grid: {NX}×{NY}",
             color="white", fontsize=12, pad=12)

plt.tight_layout()
out_preview = os.path.join(cfg.DIR_OUTPUT, "dem_mosaic_preview.png")
plt.savefig(out_preview, dpi=150, bbox_inches="tight",
            facecolor="#0a0e1a", edgecolor="none")
plt.close()
files_ok.append(out_preview)
print(f"[DONE] Modul 1.J — dem_mosaic_preview.png tersimpan")

# ── Ringkasan ─────────────────────────────────────────────────────────────────
elapsed = time.time() - t0
print("\n" + "=" * 60)
print(f"  [DONE] Modul 1 — DEM Preprocessing selesai dalam {elapsed:.1f}s")
print(f"  File berhasil : {len(files_ok)}")
for f in files_ok:
    print(f"    [OK] {os.path.basename(f)}")
if files_fail:
    print(f"  File gagal : {len(files_fail)}")
    for f in files_fail:
        print(f"    [FAIL] {f}")
print("=" * 60)
