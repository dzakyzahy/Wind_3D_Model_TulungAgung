"""
03_topo_correction.py — Modul 3: Topographic Wind Correction (Jackson-Hunt)
===========================================================================
Input : cfg.DIR_PROC\\terrain_grid.json
        cfg.DIR_PROC\\wind_climate.json
Output: cfg.DIR_PROC\\wind_corrected_3km.json
        cfg.DIR_PROC\\wind_data.json          ← untuk visualisasi browser
        cfg.DIR_OUTPUT\\wpd_corrected_vs_raw.png
"""
import sys, os, time, json, warnings
warnings.filterwarnings("ignore")
t0 = time.time()

sys.path.insert(0, r"D:\ITB2\Pak_RK\MetOcean_Tulungagung\kode_zahy\WindModel3DProject")
import config as cfg

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy import special
from scipy.ndimage import uniform_filter

files_ok   = []
files_fail = []

print("=" * 60)
print("[INFO] Modul 3 — Topographic Wind Correction (Jackson-Hunt)")

# ══════════════════════════════════════════════════════════════════════════════
# 3A. Load terrain grid
# ══════════════════════════════════════════════════════════════════════════════
def load_json(path, fallback=None):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    print(f"[WARN] {os.path.basename(path)} tidak ditemukan — pakai dummy")
    return fallback

terrain_grid = load_json(os.path.join(cfg.DIR_PROC, "terrain_grid.json"))
wind_climate = load_json(os.path.join(cfg.DIR_PROC, "wind_climate.json"))
weibull_data = load_json(os.path.join(cfg.DIR_PROC, "weibull_params.json"))

IS_DEMO = False
if terrain_grid is None:
    print("[WARN] terrain_grid.json tidak ada — membuat terrain sintetis")
    IS_DEMO = True
    NX, NZ = 100, 100
    x = np.linspace(-1, 1, NX); y = np.linspace(-1, 1, NZ)
    X, Y = np.meshgrid(x, y)
    dem_raw  = (2500 * np.exp(-((X+0.45)**2 + (Y-0.55)**2)/0.18) +
                1600 * np.exp(-((X-0.60)**2 + (Y+0.40)**2)/0.15) +
                80   * np.exp(-((X+0.1)**2 + (Y+0.15)**2)/0.25)).astype(float)
    dem_min, dem_max = float(dem_raw.min()), float(dem_raw.max())
    terrain_grid = {
        "nx": NX, "nz": NZ,
        "lat_min": cfg.LAT_MIN, "lat_max": cfg.LAT_MAX,
        "lon_min": cfg.LON_MIN, "lon_max": cfg.LON_MAX,
        "elevation_min": dem_min, "elevation_max": dem_max,
        "elevation": dem_raw.tolist(),
        "elevation_norm": ((dem_raw - dem_min)/(dem_max - dem_min + 1e-9)).tolist(),
        "is_demo": True,
    }
else:
    IS_DEMO = terrain_grid.get("is_demo", False)

NX = terrain_grid["nx"]
NZ = terrain_grid["nz"]
dem_elev = np.array(terrain_grid["elevation"], dtype=float)   # (NZ, NX)
dem_norm = np.array(terrain_grid.get("elevation_norm", 
           (dem_elev / (dem_elev.max()+1e-9))), dtype=float)
dem_min  = terrain_grid.get("elevation_min", float(dem_elev.min()))
dem_max  = terrain_grid.get("elevation_max", float(dem_elev.max()))

print(f"[INFO] Terrain grid: {NX}×{NZ} | elev {dem_min:.0f}–{dem_max:.0f}m")

# ERA5 mean wind (u, v) di grid ERA5 → perlu diinterpolasi ke terrain grid
if wind_climate is not None:
    u_era5_grid = np.array(wind_climate.get("u_mean_grid", []), dtype=float)
    v_era5_grid = np.array(wind_climate.get("v_mean_grid", []), dtype=float)
    era5_lats   = np.array(wind_climate.get("grid_lats", [cfg.SITE_LAT]), dtype=float)
    era5_lons   = np.array(wind_climate.get("grid_lons", [cfg.SITE_LON]), dtype=float)
    wspd_mean_era5 = wind_climate.get("wspd_mean_10m", 4.0)
else:
    print("[WARN] wind_climate.json tidak ada — pakai nilai default")
    u_era5_grid = np.array([[3.5]])
    v_era5_grid = np.array([[-1.0]])
    era5_lats   = np.array([cfg.SITE_LAT])
    era5_lons   = np.array([cfg.SITE_LON])
    wspd_mean_era5 = 4.0
    IS_DEMO = True

# ── Interpolasi ERA5 ke terrain grid 100×100 ─────────────────────────────────
from scipy.interpolate import RegularGridInterpolator

terrain_lats = np.linspace(cfg.LAT_MAX, cfg.LAT_MIN, NZ)
terrain_lons = np.linspace(cfg.LON_MIN, cfg.LON_MAX, NX)

if u_era5_grid.ndim == 2 and u_era5_grid.shape[0] > 1:
    # Pastikan lat direction konsisten
    era5_lats_sorted = era5_lats
    u_for_interp = u_era5_grid
    v_for_interp = v_era5_grid

    if era5_lats[0] < era5_lats[-1]:
        era5_lats_sorted = era5_lats[::-1]
        u_for_interp = u_era5_grid[::-1, :]
        v_for_interp = v_era5_grid[::-1, :]

    try:
        interp_u = RegularGridInterpolator(
            (era5_lats_sorted, era5_lons), u_for_interp,
            method="linear", bounds_error=False, fill_value=wspd_mean_era5)
        interp_v = RegularGridInterpolator(
            (era5_lats_sorted, era5_lons), v_for_interp,
            method="linear", bounds_error=False, fill_value=-1.0)

        LAT_G, LON_G = np.meshgrid(terrain_lats, terrain_lons, indexing="ij")
        pts = np.column_stack([LAT_G.ravel(), LON_G.ravel()])
        u_terrain_10m = interp_u(pts).reshape(NZ, NX)
        v_terrain_10m = interp_v(pts).reshape(NZ, NX)
    except Exception as e:
        print(f"[WARN] Interpolasi gagal: {e} — pakai uniform field")
        u_terrain_10m = np.full((NZ, NX), wspd_mean_era5 * 0.85)
        v_terrain_10m = np.full((NZ, NX), -wspd_mean_era5 * 0.25)
else:
    u_terrain_10m = np.full((NZ, NX), float(u_era5_grid.mean()) if u_era5_grid.size > 0 else 3.5)
    v_terrain_10m = np.full((NZ, NX), float(v_era5_grid.mean()) if v_era5_grid.size > 0 else -1.0)

print(f"[INFO] ERA5 @ terrain grid — u mean={u_terrain_10m.mean():.2f}, v mean={v_terrain_10m.mean():.2f} m/s")
print("[DONE] Modul 3.A — Load & interpolasi terrain selesai")

# ══════════════════════════════════════════════════════════════════════════════
# 3A.2 Hitung parameter terrain per sel
# ══════════════════════════════════════════════════════════════════════════════
# z_mean dalam window ~30 piksel (~3km pada resolusi 100×100 atas domain 2°)
WIN_MEAN = 15   # piksel ≈ 3km
WIN_ROUGH = 50  # piksel ≈ 10km

z_mean   = uniform_filter(dem_elev, size=WIN_MEAN, mode="nearest")
sigma_z  = np.sqrt(uniform_filter(dem_elev**2, size=WIN_ROUGH, mode="nearest") -
                   uniform_filter(dem_elev, size=WIN_ROUGH, mode="nearest")**2)
sigma_z  = np.maximum(sigma_z, 1.0)

# Gradien (slope)
grad_y, grad_x = np.gradient(dem_elev)
grad_mag = np.sqrt(grad_x**2 + grad_y**2)
# Normalisasi gradien ke derajat (1 piksel ≈ 1.5km)
pix_km = 1.5
slope_deg = np.degrees(np.arctan(grad_mag / (pix_km * 1000)))

# Aspek (arah lereng dominan)
aspect = (np.degrees(np.arctan2(grad_x, grad_y)) + 360) % 360

# Exposure index: fraksi piksel dalam radius 5km yang lebih rendah
WIN_EXP = 10   # ~5km radius
z_local_max = uniform_filter(dem_elev, size=WIN_EXP*2+1, mode="nearest")
exposure = np.clip((z_mean - uniform_filter(dem_elev, size=WIN_EXP, mode="nearest"))
                   / (sigma_z + 1.0) + 0.5, 0, 1)

print("[DONE] Modul 3.A.2 — Parameter terrain dihitung")

# ══════════════════════════════════════════════════════════════════════════════
# 3B. Speedup factor Jackson-Hunt (simplified)
# ══════════════════════════════════════════════════════════════════════════════
def jackson_hunt_speedup(delta_h, L, f_shape=1.0, exposure_idx=0.5):
    """
    delta_h : beda tinggi dari terrain upwind (m)
    L       : panjang karakteristik bukit (m)
    f_shape : 1.0 ridge, 0.7 rounded hill
    exposure: 0 = terlindung, 1 = sangat terekspos
    """
    ratio = np.clip(delta_h / (L + 1e-6), 0, 0.8)
    speedup = 1.0 + ratio * f_shape * exposure_idx
    return np.clip(speedup, 0.7, 1.6)

# Karakteristik terrain
# delta_h = selisih z_mean dan rata-rata sekitar (upwind ~5km)
z_bg = uniform_filter(dem_elev, size=30, mode="nearest")
delta_h = np.maximum(0, z_mean - z_bg)

# L = setengah lebar bukit (½ panjang di mana elevasi > 50% peak)
L = np.maximum(1500, sigma_z * 3.0)   # m

# f_shape: 1.0 untuk area ridge tinggi, 0.7 untuk area rendah
ridge_frac = np.clip(slope_deg / 30.0, 0, 1)
f_shape = 0.7 + 0.3 * ridge_frac

speedup = jackson_hunt_speedup(delta_h, L, f_shape, exposure)

# ── 3B.2 Roughness correction ─────────────────────────────────────────────────
# z0_local dari elevasi (proxy: pantai <10m z0=0.001, hutan z0=0.5, lahan z0=0.03)
z0_local = np.where(dem_elev < 10, cfg.Z0_COAST,
           np.where(dem_elev > 300, cfg.Z0_FOREST, cfg.Z0_ERA5))

def roughness_correction(z, z0_local, z0_era5=cfg.Z0_ERA5):
    """Ratio of log profiles (neutral stability)."""
    lnz_local = np.log(z / z0_local)
    lnz_era5  = np.log(z / z0_era5)
    return np.clip(lnz_local / lnz_era5, 0.5, 1.8)

print("[DONE] Modul 3.B — Speedup factors dihitung")
print(f"[INFO] Speedup: min={speedup.min():.3f} mean={speedup.mean():.3f} max={speedup.max():.3f}")

# ══════════════════════════════════════════════════════════════════════════════
# 3C. Apply correction ke setiap hub height
# ══════════════════════════════════════════════════════════════════════════════
hub_heights = [50, 100, 150]
wind_layers = []

for z_hub in hub_heights:
    # Power law ekstrapolasi dari 10m ke hub height
    u_hub = u_terrain_10m * (z_hub / cfg.Z_REF) ** cfg.ALPHA_ONSHORE
    v_hub = v_terrain_10m * (z_hub / cfg.Z_REF) ** cfg.ALPHA_ONSHORE

    # Roughness correction
    rc = roughness_correction(z_hub, z0_local)

    # Apply speedup + roughness
    u_corr = u_hub * speedup * rc
    v_corr = v_hub * speedup * rc
    wspd_corr = np.sqrt(u_corr**2 + v_corr**2)
    wdir_corr = (270 - np.degrees(np.arctan2(v_corr, u_corr))) % 360

    # WPD (pakai Weibull site params, adjusted by speedup)
    if weibull_data is not None:
        k_h  = weibull_data.get("hub_heights", {}).get(f"{z_hub}m", {}).get("k", 2.0)
        lam_h = weibull_data.get("hub_heights", {}).get(f"{z_hub}m", {}).get("lambda", 5.0)
    else:
        k_h, lam_h = 2.0, float(wspd_corr.mean()) / 0.8862

    # Adjust lambda by local speedup
    lam_adj = lam_h * speedup * rc
    wpd_corr = 0.5 * cfg.RHO_AIR * lam_adj**3 * special.gamma(1 + 3.0/k_h)

    wind_layers.append({
        "agl": int(z_hub),
        "u": u_corr.tolist(),
        "v": v_corr.tolist(),
        "wspd": wspd_corr.tolist(),
        "wpd": wpd_corr.tolist(),
        "wdir": wdir_corr.tolist(),
    })
    print(f"[INFO] {z_hub}m — wspd: {wspd_corr.mean():.2f}±{wspd_corr.std():.2f} m/s | "
          f"WPD: {wpd_corr.mean():.1f} W/m²")

print("[DONE] Modul 3.C — Koreksi angin selesai")

# ══════════════════════════════════════════════════════════════════════════════
# 3D. Export wind_data.json untuk browser (Three.js / Plotly)
# ══════════════════════════════════════════════════════════════════════════════
print("[INFO] Menyiapkan wind_data.json untuk browser...")

# Subsample ke 100×100 jika perlu
TARGET = 100
if NX > TARGET or NZ > TARGET:
    from scipy.ndimage import zoom as sp_zoom
    factor_x = TARGET / NX
    factor_z = TARGET / NZ
    dem_norm_sub = sp_zoom(dem_norm, (factor_z, factor_x), order=1)
    dem_elev_sub = sp_zoom(dem_elev, (factor_z, factor_x), order=1)
    layers_sub = []
    for lyr in wind_layers:
        layers_sub.append({
            "agl": lyr["agl"],
            "u":    sp_zoom(np.array(lyr["u"]),    (factor_z, factor_x), order=1).ravel().tolist(),
            "v":    sp_zoom(np.array(lyr["v"]),    (factor_z, factor_x), order=1).ravel().tolist(),
            "wspd": sp_zoom(np.array(lyr["wspd"]), (factor_z, factor_x), order=1).ravel().tolist(),
            "wpd":  sp_zoom(np.array(lyr["wpd"]),  (factor_z, factor_x), order=1).ravel().tolist(),
        })
    NX_OUT, NZ_OUT = TARGET, TARGET
else:
    dem_norm_sub = dem_norm
    dem_elev_sub = dem_elev
    layers_sub   = [{**lyr,
                     "u":    np.array(lyr["u"]).ravel().tolist(),
                     "v":    np.array(lyr["v"]).ravel().tolist(),
                     "wspd": np.array(lyr["wspd"]).ravel().tolist(),
                     "wpd":  np.array(lyr["wpd"]).ravel().tolist(),
                     } for lyr in wind_layers]
    NX_OUT, NZ_OUT = NX, NZ

# Stats dari layer 100m (index 1)
wspd_100_arr = np.array(layers_sub[1]["wspd"])
wpd_100_arr  = np.array(layers_sub[1]["wpd"])

weibull_k_out   = weibull_data.get("hub_heights",{}).get("100m",{}).get("k", 2.0) if weibull_data else 2.0
weibull_lam_out = weibull_data.get("hub_heights",{}).get("100m",{}).get("lambda", 5.0) if weibull_data else 5.0
cf_out  = weibull_data.get("cf",{}).get("100m", 0.25) if weibull_data else 0.25

wind_data_json = {
    "meta": {
        "nx": NX_OUT, "nz": NZ_OUT,
        "n_levels": len(layers_sub),
        "levels_m_agl": [l["agl"] for l in layers_sub],
        "lat_min": cfg.LAT_MIN, "lat_max": cfg.LAT_MAX,
        "lon_min": cfg.LON_MIN, "lon_max": cfg.LON_MAX,
        "elev_min_m": round(dem_min, 1), "elev_max_m": round(dem_max, 1),
        "wspd_min": round(float(wspd_100_arr.min()), 3),
        "wspd_max": round(float(wspd_100_arr.max()), 3),
        "wpd_min":  round(float(wpd_100_arr.min()), 1),
        "wpd_max":  round(float(wpd_100_arr.max()), 1),
        "data_source": "ERA5 ECMWF + DEMNAS 8m + Jackson-Hunt",
        "is_demo": IS_DEMO or terrain_grid.get("is_demo", False),
    },
    "terrain": dem_norm_sub.tolist(),  # 100×100 normalisasi 0-1
    "elevation_m": dem_elev_sub.tolist(),  # nilai asli meter
    "wind_layers": layers_sub,
    "stats": {
        "wspd_mean_10m":   round(float(wspd_mean_era5), 3),
        "wspd_mean_100m":  round(float(wspd_100_arr.mean()), 3),
        "wpd_mean_100m":   round(float(wpd_100_arr.mean()), 1),
        "cf_mean_100m":    round(float(cf_out), 4),
        "weibull_k":       round(float(weibull_k_out), 4),
        "weibull_lambda":  round(float(weibull_lam_out), 4),
        "speedup_mean":    round(float(speedup.mean()), 4),
        "is_demo": IS_DEMO or terrain_grid.get("is_demo", False),
    },
    "terrain_stats": {
        "slope_mean_deg":  round(float(slope_deg.mean()), 2),
        "exposure_mean":   round(float(exposure.mean()), 3),
        "speedup_mean":    round(float(speedup.mean()), 4),
        "speedup_max":     round(float(speedup.max()), 4),
    }
}

# Cek ukuran
import io
buf = io.StringIO()
json.dump(wind_data_json, buf, separators=(",",":"))
size_mb = len(buf.getvalue().encode()) / 1e6
print(f"[INFO] wind_data.json estimasi ukuran: {size_mb:.1f} MB")

if size_mb > 5:
    print("[INFO] Ukuran > 5MB → subsample ulang ke 80×80")
    from scipy.ndimage import zoom as sp_zoom2
    TGT2 = 80
    fx2, fz2 = TGT2/NX_OUT, TGT2/NZ_OUT
    dem_norm_sub2 = sp_zoom2(dem_norm_sub, (fz2, fx2), order=1)
    dem_elev_sub2 = sp_zoom2(dem_elev_sub, (fz2, fx2), order=1)
    layers_sub2 = []
    for lyr in layers_sub:
        arr_u = np.array(lyr["u"]).reshape(NZ_OUT, NX_OUT)
        arr_v = np.array(lyr["v"]).reshape(NZ_OUT, NX_OUT)
        arr_w = np.array(lyr["wspd"]).reshape(NZ_OUT, NX_OUT)
        arr_p = np.array(lyr["wpd"]).reshape(NZ_OUT, NX_OUT)
        layers_sub2.append({
            "agl": lyr["agl"],
            "u":    sp_zoom2(arr_u,(fz2,fx2),order=1).ravel().tolist(),
            "v":    sp_zoom2(arr_v,(fz2,fx2),order=1).ravel().tolist(),
            "wspd": sp_zoom2(arr_w,(fz2,fx2),order=1).ravel().tolist(),
            "wpd":  sp_zoom2(arr_p,(fz2,fx2),order=1).ravel().tolist(),
        })
    wind_data_json["meta"]["nx"] = TGT2
    wind_data_json["meta"]["nz"] = TGT2
    wind_data_json["terrain"]     = dem_norm_sub2.tolist()
    wind_data_json["elevation_m"] = dem_elev_sub2.tolist()
    wind_data_json["wind_layers"] = layers_sub2
    NX_OUT = NZ_OUT = TGT2

out_wd = os.path.join(cfg.DIR_PROC, "wind_data.json")
with open(out_wd, "w") as f:
    json.dump(wind_data_json, f, separators=(",",":"))
files_ok.append(out_wd)
print(f"[DONE] Modul 3.D — wind_data.json tersimpan ({os.path.getsize(out_wd)/1e6:.1f} MB)")

# Save corrected wind summary
wind_corr_summary = {
    "nx": NX_OUT, "nz": NZ_OUT,
    "speedup_mean": round(float(speedup.mean()),4),
    "speedup_std":  round(float(speedup.std()),4),
    "hub_heights_m": hub_heights,
    "wspd_mean_by_height": {
        str(lyr["agl"]): round(float(np.array(lyr["wspd"]).mean()),3)
        for lyr in wind_layers
    },
    "wpd_mean_by_height": {
        str(lyr["agl"]): round(float(np.array(lyr["wpd"]).mean()),1)
        for lyr in wind_layers
    },
    "is_demo": IS_DEMO,
}
out_wc3 = os.path.join(cfg.DIR_PROC, "wind_corrected_3km.json")
with open(out_wc3, "w") as f:
    json.dump(wind_corr_summary, f, indent=2)
files_ok.append(out_wc3)

# ══════════════════════════════════════════════════════════════════════════════
# Plot: WPD corrected vs raw
# ══════════════════════════════════════════════════════════════════════════════
print("[INFO] Membuat wpd_corrected_vs_raw.png...")
DARK_BG = "#0a0e1a"; PANEL_BG = "#0d1117"; TEXT_COL = "#e0e8ff"

fig_cmp, axes = plt.subplots(1, 3, figsize=(18, 6), facecolor=DARK_BG)
titles = ["WPD ERA5 Raw (100m)", "Speedup Factor", "WPD Corrected (100m)"]

wpd_raw = 0.5 * cfg.RHO_AIR * (
    np.sqrt(u_terrain_10m**2 + v_terrain_10m**2) * (100/cfg.Z_REF)**cfg.ALPHA_ONSHORE)**3

data_plots = [wpd_raw, speedup,
              np.array(wind_layers[1]["wpd"]) if len(wind_layers) > 1 else wpd_raw*speedup]
cmaps = ["YlOrRd", "RdYlGn", "YlOrRd"]

for ax, data, title, cmap_n in zip(axes, data_plots, titles, cmaps):
    ax.set_facecolor(PANEL_BG)
    lons_t = np.linspace(cfg.LON_MIN, cfg.LON_MAX, data.shape[1] if data.ndim==2 else NX)
    lats_t = np.linspace(cfg.LAT_MAX, cfg.LAT_MIN, data.shape[0] if data.ndim==2 else NZ)
    LON_G, LAT_G = np.meshgrid(lons_t, lats_t)
    cf = ax.contourf(LON_G, LAT_G, np.array(data).reshape(
        data.shape[0] if data.ndim==2 else NZ,
        data.shape[1] if data.ndim==2 else NX),
        levels=20, cmap=cmap_n, alpha=0.9)
    plt.colorbar(cf, ax=ax, fraction=0.05, pad=0.03).ax.tick_params(colors=TEXT_COL)
    ax.plot(cfg.SITE_LON, cfg.SITE_LAT, "v", color="#ff6b35", markersize=8,
            markeredgecolor="white", markeredgewidth=1)
    ax.set_title(title, color=TEXT_COL, fontsize=10)
    ax.tick_params(colors=TEXT_COL)
    ax.set_facecolor(PANEL_BG)
    for sp in ax.spines.values(): sp.set_color("#1e2a4a")

fig_cmp.suptitle("Topographic Wind Correction — Jackson-Hunt Speedup",
                  color=TEXT_COL, fontsize=13, y=1.01)
plt.tight_layout()
out_cmp = os.path.join(cfg.DIR_OUTPUT, "wpd_corrected_vs_raw.png")
plt.savefig(out_cmp, dpi=150, bbox_inches="tight",
            facecolor=DARK_BG, edgecolor="none")
plt.close()
files_ok.append(out_cmp)
print("[DONE] Modul 3.E — wpd_corrected_vs_raw.png tersimpan")

# ══════════════════════════════════════════════════════════════════════════════
elapsed = time.time() - t0
print("\n" + "=" * 60)
print(f"  [DONE] Modul 3 — Topographic Correction selesai dalam {elapsed:.1f}s")
print(f"  File berhasil : {len(files_ok)}")
for f in files_ok:
    print(f"    [OK] {os.path.basename(f)}")
if files_fail:
    print(f"  File gagal    : {len(files_fail)}")
    for f in files_fail: print(f"    [FAIL] {f}")
print("=" * 60)
