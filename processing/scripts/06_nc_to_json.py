"""
06_nc_to_json.py — Modul 6: Konsolidasi JSON untuk Browser
============================================================
Gabungkan semua output Modul 1–5 menjadi file siap browser:
  cfg.DIR_VIZ\\wind_data.json
  cfg.DIR_VIZ\\wake_data.json
  cfg.DIR_VIZ\\stats_summary.json

Jika ada file yang belum ada → isi dummy + "is_demo": true
"""
import sys, os, time, json, shutil, warnings
warnings.filterwarnings("ignore")
t0 = time.time()

sys.path.insert(0, r"D:\ITB2\Pak_RK\MetOcean_Tulungagung\kode_zahy\WindModel3DProject")
import config as cfg

import numpy as np

files_ok   = []
files_fail = []
is_demo    = False

print("=" * 60)
print("[INFO] Modul 6 — Konsolidasi JSON untuk Browser")

# ══════════════════════════════════════════════════════════════════════════════
# Helper
# ══════════════════════════════════════════════════════════════════════════════
def load_json(path, fallback=None, label=""):
    if os.path.exists(path):
        try:
            with open(path) as f:
                data = json.load(f)
            print(f"  [OK] {label or os.path.basename(path)}")
            return data
        except Exception as e:
            print(f"  [WARN] {os.path.basename(path)} parse error: {e}")
    else:
        print(f"  [WARN] {os.path.basename(path)} tidak ditemukan")
    return fallback

def make_demo_terrain(nx=100, nz=100):
    x = np.linspace(-1, 1, nx)
    y = np.linspace(-1, 1, nz)
    X, Y = np.meshgrid(x, y)
    dem = (np.exp(-((X+0.45)**2 + (Y-0.55)**2)/0.18) * 0.9 +
           np.exp(-((X-0.60)**2 + (Y+0.40)**2)/0.15) * 0.6)
    return np.clip(dem, 0, 1)

def make_demo_wind_layers(nx, nz, hub_heights=[50,100,150]):
    lrs = []
    for h in hub_heights:
        x = np.linspace(-1, 1, nx)
        y = np.linspace(-1, 1, nz)
        X, Y = np.meshgrid(x, y)
        scale = h / 100
        u  = (3.5 + 1.5*np.sin(X*2)*np.cos(Y)) * scale
        v  = (-1.2 + 0.8*np.cos(X)) * scale
        ws = np.sqrt(u**2 + v**2)
        wpd = 0.5 * 1.225 * ws**3
        lrs.append({
            "agl": h,
            "u":    u.ravel().tolist(),
            "v":    v.ravel().tolist(),
            "wspd": ws.ravel().tolist(),
            "wpd":  wpd.ravel().tolist(),
        })
    return lrs

# ══════════════════════════════════════════════════════════════════════════════
# Load semua intermediate files
# ══════════════════════════════════════════════════════════════════════════════
print("\n[INFO] Memuat file intermediate:")
wind_data_src = load_json(os.path.join(cfg.DIR_PROC, "wind_data.json"),     label="wind_data.json (Modul 3)")
wake_src      = load_json(os.path.join(cfg.DIR_PROC, "wake_results.json"),  label="wake_results.json (Modul 4)")
extreme_src   = load_json(os.path.join(cfg.DIR_PROC, "extreme_wind_stats.json"), label="extreme_wind_stats.json (Modul 5)")
weibull_src   = load_json(os.path.join(cfg.DIR_PROC, "weibull_params.json"),label="weibull_params.json (Modul 2)")
terrain_src   = load_json(os.path.join(cfg.DIR_PROC, "terrain_grid.json"),  label="terrain_grid.json (Modul 1)")
wind_clim_src = load_json(os.path.join(cfg.DIR_PROC, "wind_climate.json"),  label="wind_climate.json (Modul 2)")
terr_stats    = load_json(os.path.join(cfg.DIR_PROC, "terrain_stats.json"), label="terrain_stats.json (Modul 1)")
wind_corr     = load_json(os.path.join(cfg.DIR_PROC, "wind_corrected_3km.json"), label="wind_corrected_3km.json (Modul 3)")

# Periksa kelengkapan
missing = []
if wind_data_src is None: missing.append("wind_data.json")
if wake_src is None:      missing.append("wake_results.json")
if extreme_src is None:   missing.append("extreme_wind_stats.json")
if weibull_src is None:   missing.append("weibull_params.json")
if terrain_src is None:   missing.append("terrain_grid.json")

if missing:
    print(f"\n[WARN] File yang belum ada: {missing}")
    print("[WARN] Menggunakan data dummy untuk file yang hilang -> is_demo: true")
    is_demo = True

# ══════════════════════════════════════════════════════════════════════════════
# 6A. wind_data.json → visualization/
# ══════════════════════════════════════════════════════════════════════════════
print("\n[INFO] Menyiapkan wind_data.json untuk browser...")

if wind_data_src is not None:
    # Validasi struktur
    required_keys = ["meta", "terrain", "wind_layers", "stats"]
    for k in required_keys:
        if k not in wind_data_src:
            print(f"[WARN] Key '{k}' hilang dari wind_data.json — tambah dummy")
            is_demo = True
    wind_data_out = wind_data_src
else:
    print("[WARN] Membuat wind_data.json dummy...")
    NX_D, NZ_D = 80, 80
    dem_demo = make_demo_terrain(NX_D, NZ_D)
    layers_demo = make_demo_wind_layers(NX_D, NZ_D)
    wspd_100 = np.array(layers_demo[1]["wspd"])
    wpd_100  = np.array(layers_demo[1]["wpd"])
    wind_data_out = {
        "meta": {
            "nx": NX_D, "nz": NZ_D, "n_levels": 3,
            "levels_m_agl": [50, 100, 150],
            "lat_min": cfg.LAT_MIN, "lat_max": cfg.LAT_MAX,
            "lon_min": cfg.LON_MIN, "lon_max": cfg.LON_MAX,
            "elev_min_m": 0, "elev_max_m": 2500,
            "wspd_min": round(float(wspd_100.min()),2),
            "wspd_max": round(float(wspd_100.max()),2),
            "wpd_min":  round(float(wpd_100.min()),1),
            "wpd_max":  round(float(wpd_100.max()),1),
            "data_source": "DEMO SYNTHETIC",
        },
        "terrain":     dem_demo.tolist(),
        "elevation_m": (dem_demo * 2500).tolist(),
        "wind_layers": layers_demo,
        "stats": {
            "wspd_mean_10m": 4.2, "wspd_mean_100m": 6.8,
            "wpd_mean_100m": 180.0, "cf_mean_100m": 0.28,
            "weibull_k": 2.1, "weibull_lambda": 7.5,
            "is_demo": True,
        },
    }
    is_demo = True

# Tambahkan flag is_demo ke stats
wind_data_out.setdefault("stats", {})["is_demo"] = is_demo or wind_data_src is None or wind_data_src.get("meta", {}).get("is_demo", False)
if extreme_src:
    wind_data_out["stats"]["v50_ms"]  = extreme_src.get("v50_ms", 0)
    wind_data_out["stats"]["iec_class"] = extreme_src.get("iec_class", "N/A")
if weibull_src:
    wb_100 = weibull_src.get("hub_heights",{}).get("100m",{})
    wind_data_out["stats"]["weibull_k"]      = wb_100.get("k", wind_data_out["stats"].get("weibull_k",2.0))
    wind_data_out["stats"]["weibull_lambda"] = wb_100.get("lambda", wind_data_out["stats"].get("weibull_lambda",5.0))
if wind_clim_src:
    wind_data_out["stats"]["wspd_mean_100m"] = wind_clim_src.get("wspd_mean_100m",
                                               wind_data_out["stats"].get("wspd_mean_100m", 6.5))
    wind_data_out["stats"]["wpd_mean_100m"]  = wind_clim_src.get("wpd_100m_wm2",
                                               wind_data_out["stats"].get("wpd_mean_100m", 180))
    wind_data_out["stats"]["cf_mean_100m"]   = wind_clim_src.get("cf_100m",
                                               wind_data_out["stats"].get("cf_mean_100m", 0.28))

out_wd_viz = os.path.join(cfg.DIR_VIZ, "wind_data.json")
with open(out_wd_viz, "w") as f:
    json.dump(wind_data_out, f, separators=(",",":"))
sz = os.path.getsize(out_wd_viz) / 1e6
files_ok.append(out_wd_viz)
print(f"[DONE] wind_data.json tersimpan ({sz:.1f} MB)")

# ══════════════════════════════════════════════════════════════════════════════
# 6B. wake_data.json → visualization/
# ══════════════════════════════════════════════════════════════════════════════
print("\n[INFO] Menyiapkan wake_data.json...")

if wake_src is not None:
    wake_data_out = wake_src
else:
    # Dummy wake data
    dummy_D  = cfg.ROTOR_DIAMETER
    dummy_pos = [[i*7*dummy_D, j*7*dummy_D] for i in range(5) for j in range(5)]
    wake_data_out = {
        "is_demo": True,
        "farm_center": {"lat": cfg.SITE_LAT, "lon": cfg.SITE_LON},
        "rotor_diameter_m": cfg.ROTOR_DIAMETER,
        "hub_height_m": cfg.HUB_HEIGHT_REF,
        "rated_kw": cfg.P_RATED,
        "layouts": {
            "A_grid_7D":  {"aep_gwh": 210, "wake_loss_pct": 8.5, "farm_area_km2": 1.1, "efficiency_pct": 91.5},
            "B_grid_10D": {"aep_gwh": 215, "wake_loss_pct": 4.2, "farm_area_km2": 2.25, "efficiency_pct": 95.8},
            "C_ridge":    {"aep_gwh": 208, "wake_loss_pct": 6.1, "farm_area_km2": 1.8, "efficiency_pct": 93.9},
        },
        "best_layout": "B_grid_10D",
        "turbine_positions_m": dummy_pos,
        "optimal_spacing_D": 10,
    }
    is_demo = True

wake_data_out["is_demo"] = is_demo or wake_src is None

out_wk_viz = os.path.join(cfg.DIR_VIZ, "wake_data.json")
with open(out_wk_viz, "w") as f:
    json.dump(wake_data_out, f, indent=2)
files_ok.append(out_wk_viz)
print(f"[DONE] wake_data.json tersimpan")

# ══════════════════════════════════════════════════════════════════════════════
# 6C. stats_summary.json → visualization/
# ══════════════════════════════════════════════════════════════════════════════
print("\n[INFO] Menyiapkan stats_summary.json...")

# Kumpulkan dari semua sumber
def safe(d, *keys, default=None):
    try:
        v = d
        for k in keys: v = v[k]
        return v
    except (TypeError, KeyError):
        return default

# Nilai kunci
wspd_mean_100 = (safe(wind_clim_src, "wspd_mean_100m", default=None) or
                 safe(wind_data_out, "stats", "wspd_mean_100m", default=6.5))
wpd_100       = (safe(wind_clim_src, "wpd_100m_wm2", default=None) or
                 safe(wind_data_out, "stats", "wpd_mean_100m", default=180))
cf_100        = (safe(wind_clim_src, "cf_100m", default=None) or
                 safe(wind_data_out, "stats", "cf_mean_100m", default=0.28))
k_100         = safe(weibull_src, "hub_heights", "100m", "k", default=2.0)
lam_100       = safe(weibull_src, "hub_heights", "100m", "lambda", default=6.5)
v50           = safe(extreme_src, "v50_ms", default=28.0)
v_ref         = safe(extreme_src, "v_ref_ms", default=round(v50*1.4, 1))
iec_class     = safe(extreme_src, "iec_class", default="III")
best_layout   = safe(wake_data_out, "best_layout", default="B_grid_10D")
best_aep      = safe(wake_data_out, "layouts", best_layout, "aep_gwh", default=215)
best_wake     = safe(wake_data_out, "layouts", best_layout, "wake_loss_pct", default=5.0)
trend         = safe(wind_clim_src, "trend_ms_per_decade", default=0.0)

# Rekomendasi kelayakan
if wspd_mean_100 >= 6.5:
    rekomendasi = "Layak dikembangkan (kelas angin cukup)"
elif wspd_mean_100 >= 5.5:
    rekomendasi = "Perlu kajian lebih lanjut (potensi marginal)"
else:
    rekomendasi = "Kurang layak untuk PLTB skala besar"

stats_summary = {
    "project": "Wind Resource Assessment Tulungagung",
    "client": "PLN",
    "site": cfg.SITE_NAME,
    "lat": cfg.SITE_LAT, "lon": cfg.SITE_LON,
    "data_source": "ERA5 ECMWF 1980–2025 + DEMNAS 8m + Jackson-Hunt",
    "is_demo": is_demo,

    "wind_resource": {
        "wspd_mean_10m_ms":   round(float(safe(wind_clim_src, "wspd_mean_10m", default=4.2) or 4.2), 3),
        "wspd_mean_100m_ms":  round(float(wspd_mean_100), 3),
        "wpd_mean_100m_wm2":  round(float(wpd_100), 1),
        "cf_100m":            round(float(cf_100), 4),
        "weibull_k_100m":     round(float(k_100), 4),
        "weibull_lambda_100m": round(float(lam_100), 4),
        "trend_ms_per_decade": round(float(trend), 4),
        "seasonal": safe(wind_clim_src, "seasonal_ms", default={"DJF":4.5,"JJA":5.5}),
    },
    "extreme_wind": {
        "v50_ms": round(float(v50), 2),
        "v_ref_ms": round(float(v_ref), 2),
        "iec_class": iec_class,
        "iec_description": f"IEC Wind Class {iec_class}",
        "v10_ms":  safe(extreme_src, "return_periods", "10", "speed_ms", default=round(v50*0.85,1)),
        "v25_ms":  safe(extreme_src, "return_periods", "25", "speed_ms", default=round(v50*0.93,1)),
        "v100_ms": safe(extreme_src, "return_periods", "100", "speed_ms", default=round(v50*1.08,1)),
    },
    "wake_and_farm": {
        "best_layout": best_layout,
        "aep_gwh_yr": best_aep,
        "wake_loss_pct": best_wake,
        "n_turbines": 25,
        "rotor_diameter_m": cfg.ROTOR_DIAMETER,
        "rated_kw": cfg.P_RATED,
        "hub_height_m": cfg.HUB_HEIGHT_REF,
        "layouts_summary": safe(wake_data_out, "layouts", default={}),
        "optimal_spacing_D": safe(wake_data_out, "optimal_spacing_D", default=10),
    },
    "terrain": {
        "dem_source": "DEMNAS BIG Indonesia 8m",
        "elevation_min_m": safe(terrain_src, "elevation_min", default=0),
        "elevation_max_m": safe(terrain_src, "elevation_max", default=2552),
        "area_above_500m_km2": safe(terr_stats, "area_above_500m", default=800),
        "peak_lat": safe(terr_stats, "peak_lat", default=-7.82),
        "peak_lon": safe(terr_stats, "peak_lon", default=111.85),
    },
    "rekomendasi": rekomendasi,
    "methodology": [
        "Sumber data: ERA5 ECMWF 1980–2025 (0.125° hourly)",
        "DEM: DEMNAS BIG Indonesia 8m resolusi",
        "Ekstrapolasi: Power Law α=0.20 (onshore)",
        "Downscaling: Jackson-Hunt topographic speedup + roughness correction",
        "Statistik: Weibull 2-parameter MLE (scipy.stats)",
        "WPD: 0.5×ρ×λ³×Γ(1+3/k)",
        "Wake: Jensen/Park top-hat model",
        "Extreme wind: Gumbel GEV pada annual maxima",
        "IEC class: V_ref = 1.4 × V_50yr",
    ],
    "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S+07:00"),
}

out_ss_viz = os.path.join(cfg.DIR_VIZ, "stats_summary.json")
with open(out_ss_viz, "w") as f:
    json.dump(stats_summary, f, indent=2)
files_ok.append(out_ss_viz)
print(f"[DONE] stats_summary.json tersimpan")

# Save JavaScript bundle for local file:// CORS bypass
out_js_viz = os.path.join(cfg.DIR_VIZ, "data_bundle.js")
print("\n[INFO] Menyiapkan data_bundle.js untuk lokal tanpa server (CORS bypass)...")
with open(out_js_viz, "w", encoding="utf-8") as f:
    f.write("window.WIND_DATA_BUNDLE = {\n")
    f.write("  windData: ")
    json.dump(wind_data_out, f, separators=(",",":"))
    f.write(",\n  wakeData: ")
    json.dump(wake_data_out, f, separators=(",",":"))
    f.write(",\n  statsSummary: ")
    json.dump(stats_summary, f, separators=(",",":"))
    f.write("\n};\n")
files_ok.append(out_js_viz)
print(f"[DONE] data_bundle.js tersimpan ({os.path.getsize(out_js_viz)/1e6:.1f} MB)")

# ══════════════════════════════════════════════════════════════════════════════
# Print ringkasan akhir
# ══════════════════════════════════════════════════════════════════════════════
elapsed = time.time() - t0
print("\n" + "=" * 60)
print(f"  [DONE] Modul 6 — JSON Konsolidasi selesai dalam {elapsed:.1f}s")
print(f"  File berhasil : {len(files_ok)}")
for f in files_ok:
    sz = os.path.getsize(f) if os.path.exists(f) else 0
    print(f"    [OK] {os.path.basename(f)} ({sz/1024:.1f} KB)")
if files_fail:
    for f in files_fail: print(f"    [FAIL] {f}")
if is_demo:
    print(f"\n  [WARN] DEMO MODE aktif — beberapa data menggunakan nilai dummy")
    print(f"         Jalankan Modul 1–5 dengan data nyata untuk hasil aktual")
print("\n  Ringkasan kunci:")
print(f"    Kecepatan angin rata-rata @100m : {round(float(wspd_mean_100),2)} m/s")
print(f"    WPD @100m                       : {round(float(wpd_100),1)} W/m²")
print(f"    Capacity Factor                 : {round(float(cf_100)*100,1)}%")
print(f"    V50-year                        : {round(float(v50),1)} m/s")
print(f"    IEC Class                       : {iec_class}")
print(f"    AEP (layout terbaik, 25 turbin) : {best_aep} GWh/yr")
print(f"    Rekomendasi                     : {rekomendasi}")
print("=" * 60)
print(f"\nBuka visualisasi: {os.path.join(cfg.DIR_VIZ, 'index.html')}")
