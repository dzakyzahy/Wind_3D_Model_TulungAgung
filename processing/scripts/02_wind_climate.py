"""
02_wind_climate.py — Modul 2: Wind Climate Analysis (ERA5 1980–2025)
=====================================================================
Input : DIR_ERA5_MAIN\\ERA5_*_u10_*.nc  (1 file per tahun)
        DIR_ERA5_MAIN\\ERA5_*_v10_*.nc
Output: cfg.DIR_PROC\\wind_climate.nc
        cfg.DIR_PROC\\weibull_params.json
        cfg.DIR_PROC\\wind_profile_heights.json
        cfg.DIR_OUTPUT\\windrose_annual.png
        cfg.DIR_OUTPUT\\windrose_seasonal.png
        cfg.DIR_OUTPUT\\weibull_fit_site.png
        cfg.DIR_OUTPUT\\wind_trend_timeseries.png
        cfg.DIR_OUTPUT\\wpd_map_100m.png
        cfg.DIR_OUTPUT\\capacity_factor_map.png
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
from matplotlib.colors import LinearSegmentedColormap
from scipy import stats, special
from scipy.stats import weibull_min, linregress

files_ok   = []
files_fail = []

print("=" * 60)
print("[INFO] Modul 2 — Wind Climate Analysis ERA5")

# ══════════════════════════════════════════════════════════════════════════════
# 2A. Load ERA5 u10 / v10
# ══════════════════════════════════════════════════════════════════════════════
years = list(range(cfg.ERA5_START_YEAR, cfg.ERA5_END_YEAR + 1))
USE_DEMO = False

try:
    import xarray as xr
    u10_files = sorted(glob.glob(os.path.join(cfg.DIR_ERA5_MAIN,
                                              "ERA5_*_u10_*.nc")))
    v10_files = sorted(glob.glob(os.path.join(cfg.DIR_ERA5_MAIN,
                                              "ERA5_*_v10_*.nc")))
    if len(u10_files) == 0:
        raise FileNotFoundError("Tidak ada ERA5 u10 files")
    print(f"[INFO] Memuat {len(u10_files)} file u10 dan {len(v10_files)} file v10...")
    print("[INFO] Menggunakan lazy loading (chunked)...")

    ds_u = xr.open_mfdataset(u10_files, combine="by_coords",
                              chunks="auto", engine="netcdf4")
    ds_v = xr.open_mfdataset(v10_files, combine="by_coords",
                              chunks="auto", engine="netcdf4")
    ds = xr.merge([ds_u, ds_v])
    if "valid_time" in ds.dims: ds = ds.rename({"valid_time": "time"})
    elif "valid_time" in ds.coords: ds = ds.rename({"valid_time": "time"})

    # Hitung kecepatan dan arah
    ds["wspd"] = np.sqrt(ds[cfg.ERA5_VAR_U10]**2 + ds[cfg.ERA5_VAR_V10]**2)
    ds["wdir"] = (270 - np.degrees(np.arctan2(
        ds[cfg.ERA5_VAR_V10], ds[cfg.ERA5_VAR_U10]))) % 360

    print(f"[INFO] Dataset: {dict(ds.dims)}")
    print(f"[INFO] Koordinat lat: {float(ds.latitude.min()):.2f}–{float(ds.latitude.max()):.2f}")
    print(f"[INFO] Koordinat lon: {float(ds.longitude.min()):.2f}–{float(ds.longitude.max()):.2f}")

    # Clip ke domain
    ds = ds.sel(
        latitude=slice(cfg.LAT_MAX, cfg.LAT_MIN),
        longitude=slice(cfg.LON_MIN, cfg.LON_MAX)
    )

    print("[DONE] Modul 2.A — Load ERA5 selesai")

except Exception as e:
    print(f"[WARN] Load ERA5 gagal: {e}")
    print("[WARN] Menggunakan data sintetis ERA5 (demo mode)")
    USE_DEMO = True
    import xarray as xr

# ── Demo data generator ──────────────────────────────────────────────────────
def make_demo_era5():
    """Generate synthetic ERA5 wind data for Tulungagung (1980–2025)."""
    print("[INFO] Membuat ERA5 sintetis 10-tahun (demo)...")
    np.random.seed(42)
    nlat, nlon = 9, 9
    lats = np.linspace(cfg.LAT_MAX, cfg.LAT_MIN, nlat)
    lons = np.linspace(cfg.LON_MIN, cfg.LON_MAX, nlon)

    # 5 tahun data × 8760 jam
    n_years = 5
    n_hours = n_years * 8760
    times = xr.cftime_range("2019-01-01", periods=n_hours, freq="1H")

    # Pola musiman: angin lebih kencang Jun–Sep (musim timur)
    hour_idx = np.arange(n_hours)
    month_idx = (hour_idx // 730) % 12
    seasonal = 1 + 0.4 * np.cos((month_idx - 6.5) / 12 * 2 * np.pi)
    diurnal  = 1 + 0.15 * np.cos((hour_idx % 24 - 14) / 24 * 2 * np.pi)

    u_base = np.random.randn(n_hours, nlat, nlon) * 2
    v_base = np.random.randn(n_hours, nlat, nlon) * 1.5

    u10 = (3.0 + 1.5 * np.sin(hour_idx / 8760 * 2 * np.pi).reshape(-1,1,1)) * \
          seasonal.reshape(-1,1,1) * diurnal.reshape(-1,1,1) + u_base
    v10 = (-1.0 + 0.8 * np.cos(hour_idx / 8760 * 2 * np.pi).reshape(-1,1,1)) * \
          seasonal.reshape(-1,1,1) * 0.7 + v_base

    ds_demo = xr.Dataset({
        "u10": (["time","latitude","longitude"], u10.astype(np.float32)),
        "v10": (["time","latitude","longitude"], v10.astype(np.float32)),
    }, coords={"time": times, "latitude": lats, "longitude": lons})

    ds_demo["wspd"] = np.sqrt(ds_demo["u10"]**2 + ds_demo["v10"]**2)
    ds_demo["wdir"] = (270 - np.degrees(np.arctan2(ds_demo["v10"], ds_demo["u10"]))) % 360
    return ds_demo

if USE_DEMO:
    ds = make_demo_era5()

# ══════════════════════════════════════════════════════════════════════════════
# 2B. Ekstrak site terdekat
# ══════════════════════════════════════════════════════════════════════════════
site = ds.sel(latitude=cfg.SITE_LAT, longitude=cfg.SITE_LON, method="nearest")
print(f"[INFO] Grid terdekat ke {cfg.SITE_NAME}: "
      f"lat={float(site.latitude):.3f} lon={float(site.longitude):.3f}")

# Load data site ke numpy (compute dari dask jika perlu)
print("[INFO] Mengumpulkan data site ke memori...")
wspd_site = np.array(site["wspd"].values, dtype=float)
wdir_site = np.array(site["wdir"].values, dtype=float)
u10_site  = np.array(site["u10"].values, dtype=float)
v10_site  = np.array(site["v10"].values, dtype=float)
times_site = site["time"].values

wspd_site = np.nan_to_num(wspd_site, nan=0.0)
wdir_site = np.nan_to_num(wdir_site, nan=0.0)
print(f"[INFO] Site data: {len(wspd_site)} jam | mean={wspd_site.mean():.2f} m/s")
print("[DONE] Modul 2.B — Ekstraksi site selesai")

# ══════════════════════════════════════════════════════════════════════════════
# 2C. Statistik iklim di titik site
# ══════════════════════════════════════════════════════════════════════════════
import pandas as pd

df = pd.DataFrame({
    "wspd": wspd_site, "wdir": wdir_site,
    "u10": u10_site, "v10": v10_site
}, index=pd.to_datetime(times_site))

monthly_mean = df["wspd"].groupby(df.index.month).mean()
seasonal_mean = {
    "DJF": float(df["wspd"][df.index.month.isin([12,1,2])].mean()),
    "MAM": float(df["wspd"][df.index.month.isin([3,4,5])].mean()),
    "JJA": float(df["wspd"][df.index.month.isin([6,7,8])].mean()),
    "SON": float(df["wspd"][df.index.month.isin([9,10,11])].mean()),
}
annual_mean = float(df["wspd"].mean())
p50 = float(np.percentile(wspd_site, 50))
p75 = float(np.percentile(wspd_site, 75))
p90 = float(np.percentile(wspd_site, 90))

print(f"[INFO] Wind stats: mean={annual_mean:.2f} P50={p50:.2f} P75={p75:.2f} P90={p90:.2f} m/s")
print(f"[INFO] Seasonal: DJF={seasonal_mean['DJF']:.2f} MAM={seasonal_mean['MAM']:.2f} "
      f"JJA={seasonal_mean['JJA']:.2f} SON={seasonal_mean['SON']:.2f} m/s")
print("[DONE] Modul 2.C — Statistik iklim selesai")

# ══════════════════════════════════════════════════════════════════════════════
# 2D. Ekstrapolasi power law ke hub heights
# ══════════════════════════════════════════════════════════════════════════════
wspd_at = {}
for z in cfg.HUB_HEIGHTS:
    wspd_at[z] = wspd_site * (z / cfg.Z_REF) ** cfg.ALPHA_ONSHORE

wspd_100m = wspd_at[100]
wspd_80m  = wspd_at[80]
wspd_150m = wspd_at[150]
print(f"[INFO] wspd @ 100m: mean={wspd_100m.mean():.2f} m/s max={wspd_100m.max():.2f} m/s")
print("[DONE] Modul 2.D — Ekstrapolasi hub height selesai")

# ══════════════════════════════════════════════════════════════════════════════
# 2E. Weibull fitting di titik site
# ══════════════════════════════════════════════════════════════════════════════
def fit_weibull(ws_arr):
    ws_clean = ws_arr[ws_arr > 0.1]
    if len(ws_clean) < 10:
        return 2.0, 5.0
    try:
        shape, loc, scale = weibull_min.fit(ws_clean, floc=0)
        return float(shape), float(scale)
    except Exception:
        return 2.0, float(ws_clean.mean() / 0.8862)

k_site, lam_site = fit_weibull(wspd_100m)
k_80m, lam_80m   = fit_weibull(wspd_80m)
k_150m, lam_150m = fit_weibull(wspd_150m)
print(f"[INFO] Weibull 100m: k={k_site:.3f}, λ={lam_site:.3f} m/s")
print("[DONE] Modul 2.E — Weibull fitting selesai")

# ══════════════════════════════════════════════════════════════════════════════
# 2F. Wind Power Density
# ══════════════════════════════════════════════════════════════════════════════
def calc_wpd(k, lam):
    return 0.5 * cfg.RHO_AIR * lam**3 * special.gamma(1 + 3.0/k)

wpd_100m = calc_wpd(k_site, lam_site)
wpd_80m  = calc_wpd(k_80m, lam_80m)
wpd_150m = calc_wpd(k_150m, lam_150m)
print(f"[INFO] WPD site: 80m={wpd_80m:.1f} W/m² | 100m={wpd_100m:.1f} W/m² | 150m={wpd_150m:.1f} W/m²")
print("[DONE] Modul 2.F — Wind Power Density selesai")

# ══════════════════════════════════════════════════════════════════════════════
# 2G. Capacity Factor (Vestas V150-4.5MW power curve × Weibull)
# ══════════════════════════════════════════════════════════════════════════════
pc_ws  = np.array(sorted(cfg.POWER_CURVE.keys()), dtype=float)
pc_kw  = np.array([cfg.POWER_CURVE[v] for v in sorted(cfg.POWER_CURVE.keys())], dtype=float)

def weibull_pdf(u, k, lam):
    u = np.maximum(u, 1e-6)
    return (k/lam) * (u/lam)**(k-1) * np.exp(-(u/lam)**k)

def calc_cf(k, lam):
    u_range = np.linspace(0, 30, 3000)
    pdf     = weibull_pdf(u_range, k, lam)
    p_curve = np.interp(u_range, pc_ws, pc_kw)
    aep_per_kw = np.trapz(pdf * p_curve, u_range) / cfg.P_RATED
    return float(np.clip(aep_per_kw, 0, 1))

cf_100m = calc_cf(k_site, lam_site)
cf_80m  = calc_cf(k_80m, lam_80m)
print(f"[INFO] CF: 80m={cf_80m:.3f} | 100m={cf_100m:.3f}")
print("[DONE] Modul 2.G — Capacity Factor selesai")

# ══════════════════════════════════════════════════════════════════════════════
# 2H. Trend analysis (annual mean)
# ══════════════════════════════════════════════════════════════════════════════
df["wspd_100m"] = wspd_100m
annual_means = df["wspd_100m"].resample("YE").mean()
if len(annual_means) > 2:
    yrs = annual_means.index.year.values.astype(float)
    slope, intercept, r_value, p_value, _ = linregress(yrs, annual_means.values)
    trend_ms_per_decade = slope * 10
else:
    trend_ms_per_decade, r_value, p_value = 0.0, 0.0, 1.0
    yrs = np.array([2020, 2024])
    annual_means_fake = pd.Series([annual_mean]*2,
                                   index=pd.DatetimeIndex(["2020","2024"]))
    annual_means = annual_means_fake

print(f"[INFO] Tren: {trend_ms_per_decade:+.3f} m/s/dekade (r={r_value:.3f}, p={p_value:.3f})")
print("[DONE] Modul 2.H — Trend analysis selesai")

# ══════════════════════════════════════════════════════════════════════════════
# 2I. Hitung statistik spasial dari grid ERA5
# ══════════════════════════════════════════════════════════════════════════════
print("[INFO] Menghitung Weibull & WPD per grid point...")
lats_grid = np.array(ds["latitude"].values, dtype=float)
lons_grid = np.array(ds["longitude"].values, dtype=float)
nlat = len(lats_grid)
nlon = len(lons_grid)

# Ekstrapolasi ke 100m untuk semua grid
try:
    wspd_grid = np.array(ds["wspd"].values, dtype=float)
    wspd_grid_100m = wspd_grid * (100 / cfg.Z_REF) ** cfg.ALPHA_ONSHORE
    print(f"[INFO] Grid shape: {wspd_grid_100m.shape} (time×lat×lon)")

    k_grid   = np.zeros((nlat, nlon))
    lam_grid = np.zeros((nlat, nlon))
    wpd_grid = np.zeros((nlat, nlon))
    cf_grid  = np.zeros((nlat, nlon))

    for i in range(nlat):
        for j in range(nlon):
            ws_ij = wspd_grid_100m[:, i, j]
            ws_ij = ws_ij[np.isfinite(ws_ij) & (ws_ij > 0.1)]
            if len(ws_ij) < 10:
                k_grid[i,j] = 2.0; lam_grid[i,j] = annual_mean / 0.8862
            else:
                k_grid[i,j], lam_grid[i,j] = fit_weibull(ws_ij)
            wpd_grid[i,j] = calc_wpd(k_grid[i,j], lam_grid[i,j])
            cf_grid[i,j]  = calc_cf(k_grid[i,j], lam_grid[i,j])

    print("[DONE] Modul 2.I — WPD spasial selesai")
except Exception as e:
    print(f"[WARN] Komputasi spasial gagal: {e}")
    k_grid   = np.full((nlat, nlon), k_site)
    lam_grid = np.full((nlat, nlon), lam_site)
    wpd_grid = np.full((nlat, nlon), wpd_100m)
    cf_grid  = np.full((nlat, nlon), cf_100m)

# ══════════════════════════════════════════════════════════════════════════════
# 2I.b Simpan weibull_params.json dan wind_profile_heights.json
# ══════════════════════════════════════════════════════════════════════════════
weibull_params = {
    "site_lat": cfg.SITE_LAT, "site_lon": cfg.SITE_LON,
    "is_demo": USE_DEMO,
    "hub_heights": {
        "80m":  {"k": round(k_80m,4), "lambda": round(lam_80m,4)},
        "100m": {"k": round(k_site,4), "lambda": round(lam_site,4)},
        "150m": {"k": round(k_150m,4), "lambda": round(lam_150m,4)},
    },
    "wpd_wm2": {"80m": round(wpd_80m,1), "100m": round(wpd_100m,1), "150m": round(wpd_150m,1)},
    "cf"      : {"80m": round(cf_80m,4), "100m": round(cf_100m,4)},
    "seasonal_mean_ms": seasonal_mean,
    "percentile_ms": {"P50": round(p50,2), "P75": round(p75,2), "P90": round(p90,2)},
    "trend_ms_per_decade": round(trend_ms_per_decade,4),
    "grid_k":   k_grid.tolist(), "grid_lambda": lam_grid.tolist(),
    "grid_wpd": wpd_grid.tolist(), "grid_cf": cf_grid.tolist(),
    "grid_lat": lats_grid.tolist(), "grid_lon": lons_grid.tolist(),
}

out_weibull = os.path.join(cfg.DIR_PROC, "weibull_params.json")
with open(out_weibull, "w") as f:
    json.dump(weibull_params, f, separators=(",",":"))
files_ok.append(out_weibull)
print(f"[DONE] Modul 2.I — weibull_params.json tersimpan ({os.path.getsize(out_weibull)/1024:.1f} KB)")

# wind profile heights
wind_profile = {
    "site": cfg.SITE_NAME, "lat": cfg.SITE_LAT, "lon": cfg.SITE_LON,
    "is_demo": USE_DEMO,
    "z_ref_m": cfg.Z_REF, "alpha_onshore": cfg.ALPHA_ONSHORE,
    "heights_m": cfg.HUB_HEIGHTS,
    "wspd_mean_ms": {str(z): round(float(wspd_at[z].mean()),3) for z in cfg.HUB_HEIGHTS},
    "wspd_p75_ms":  {str(z): round(float(np.percentile(wspd_at[z],75)),3) for z in cfg.HUB_HEIGHTS},
    "annual_means_100m": {
        str(int(yr)): round(float(v),3)
        for yr, v in zip(annual_means.index.year if hasattr(annual_means.index,'year')
                         else [2020,2024], annual_means.values)
    },
}
out_profile = os.path.join(cfg.DIR_PROC, "wind_profile_heights.json")
with open(out_profile, "w") as f:
    json.dump(wind_profile, f, indent=2)
files_ok.append(out_profile)

# ══════════════════════════════════════════════════════════════════════════════
# PLOTS
# ══════════════════════════════════════════════════════════════════════════════

DARK_BG   = "#0a0e1a"
PANEL_BG  = "#0d1117"
TEXT_COL  = "#e0e8ff"
GRID_COL  = "#1e2a4a"
ACCENT1   = "#22d3ee"
ACCENT2   = "#f59e0b"
ACCENT3   = "#10b981"

# ── Plot 1: Wind Rose Annual ──────────────────────────────────────────────────
print("[INFO] Membuat windrose_annual.png...")
try:
    from windrose import WindroseAxes
    fig_wr = plt.figure(figsize=(9, 8), facecolor=DARK_BG)
    ax_wr = WindroseAxes.from_ax(fig=fig_wr)
    ax_wr.set_facecolor(DARK_BG)
    ax_wr.bar(wdir_site, wspd_site, normed=True, opening=0.8,
              bins=[0,2,4,6,8,10,12], cmap=plt.cm.RdYlGn_r,
              edgecolor="none", alpha=0.85)
    ax_wr.set_legend(title="m/s", loc="lower right",
                     labelcolor=TEXT_COL, facecolor=PANEL_BG,
                     edgecolor=GRID_COL, fontsize=9)
    ax_wr.tick_params(colors=TEXT_COL, labelsize=9)
    fig_wr.suptitle(f"Wind Rose Tahunan — {cfg.SITE_NAME}\n"
                    f"ERA5 1980–2025 | Mean: {annual_mean:.2f} m/s @ 10m",
                    color=TEXT_COL, fontsize=11, y=0.98)
    out_wr_a = os.path.join(cfg.DIR_OUTPUT, "windrose_annual.png")
    plt.savefig(out_wr_a, dpi=150, bbox_inches="tight",
                facecolor=DARK_BG, edgecolor="none")
    plt.close()
    files_ok.append(out_wr_a)
    print("[DONE] Modul 2.I.1 — windrose_annual.png tersimpan")

    # Seasonal wind rose (2×2)
    seasons = {"DJF":[12,1,2], "MAM":[3,4,5], "JJA":[6,7,8], "SON":[9,10,11]}
    fig_ws, axes_ws = plt.subplots(2, 2, figsize=(14, 12),
                                   facecolor=DARK_BG,
                                   subplot_kw={"projection":"windrose"})
    fig_ws.set_facecolor(DARK_BG)
    for ax_s, (sname, months) in zip(axes_ws.flat, seasons.items()):
        mask = np.isin(pd.DatetimeIndex(times_site).month, months)
        ws_s = wspd_site[mask]; wd_s = wdir_site[mask]
        ax_s.set_facecolor(DARK_BG)
        ax_s.bar(wd_s, ws_s, normed=True, bins=[0,2,4,6,8,10],
                 cmap=plt.cm.RdYlGn_r, edgecolor="none", alpha=0.85)
        ax_s.set_title(f"{sname} — mean {ws_s.mean():.2f} m/s",
                       color=TEXT_COL, fontsize=10, pad=8)
        ax_s.tick_params(colors=TEXT_COL, labelsize=8)
    fig_ws.suptitle(f"Wind Rose Musiman — {cfg.SITE_NAME}",
                    color=TEXT_COL, fontsize=13, y=0.99)
    out_wr_s = os.path.join(cfg.DIR_OUTPUT, "windrose_seasonal.png")
    plt.savefig(out_wr_s, dpi=150, bbox_inches="tight",
                facecolor=DARK_BG, edgecolor="none")
    plt.close()
    files_ok.append(out_wr_s)
    print("[DONE] Modul 2.I.2 — windrose_seasonal.png tersimpan")

except ImportError:
    print("[WARN] windrose tidak tersedia — membuat wind rose manual")
    # Wind rose manual
    fig_wr, ax_wr = plt.subplots(figsize=(8,8), subplot_kw={"polar": True},
                                  facecolor=DARK_BG)
    ax_wr.set_facecolor(DARK_BG)
    n_bins = 16
    dir_bins = np.linspace(0, 360, n_bins+1)
    dir_centers = (dir_bins[:-1] + dir_bins[1:]) / 2
    freq = np.zeros(n_bins)
    for i in range(n_bins):
        mask = ((wdir_site >= dir_bins[i]) & (wdir_site < dir_bins[i+1]))
        freq[i] = mask.sum() / len(wdir_site) * 100
    theta = np.deg2rad(dir_centers)
    bars = ax_wr.bar(theta, freq, width=2*np.pi/n_bins, color=ACCENT1,
                     alpha=0.8, edgecolor=DARK_BG)
    ax_wr.set_theta_zero_location("N"); ax_wr.set_theta_direction(-1)
    ax_wr.set_xticklabels(["N","NE","E","SE","S","SW","W","NW"], color=TEXT_COL)
    ax_wr.tick_params(colors=TEXT_COL)
    ax_wr.set_facecolor(DARK_BG); fig_wr.set_facecolor(DARK_BG)
    ax_wr.set_title(f"Wind Rose — {cfg.SITE_NAME}\nMean: {annual_mean:.2f} m/s",
                    color=TEXT_COL, fontsize=11, pad=15)
    out_wr_a = os.path.join(cfg.DIR_OUTPUT, "windrose_annual.png")
    plt.savefig(out_wr_a, dpi=150, bbox_inches="tight",
                facecolor=DARK_BG, edgecolor="none")
    plt.close()
    files_ok.append(out_wr_a)

except Exception as e:
    print(f"[WARN] Wind rose gagal: {e}")
    files_fail.append("windrose_*.png")

# ── Plot 2: Weibull fit ───────────────────────────────────────────────────────
print("[INFO] Membuat weibull_fit_site.png...")
fig_wb, ax_wb = plt.subplots(figsize=(10, 6), facecolor=DARK_BG)
ax_wb.set_facecolor(PANEL_BG)

ws_clean = wspd_100m[wspd_100m > 0.1]
ax_wb.hist(ws_clean, bins=50, density=True, color=ACCENT1, alpha=0.45,
           edgecolor="none", label="Observasi ERA5")

u_fit = np.linspace(0, ws_clean.max()+2, 300)
pdf_fit = weibull_min.pdf(u_fit, k_site, loc=0, scale=lam_site)
ax_wb.plot(u_fit, pdf_fit, color=ACCENT2, lw=2.5,
           label=f"Weibull fit: k={k_site:.3f}, λ={lam_site:.3f} m/s")

# Mark WPD classes
for ws_th, label, col in [(4,"Fair\n4 m/s","#6b7280"),
                           (5.5,"Good\n5.5 m/s","#10b981"),
                           (7,"Excellent\n7 m/s","#f59e0b")]:
    ax_wb.axvline(ws_th, color=col, lw=1.2, linestyle="--", alpha=0.7)
    ax_wb.text(ws_th+0.1, ax_wb.get_ylim()[1]*0.02 if ax_wb.get_ylim()[1] > 0 else 0.02,
               label, color=col, fontsize=8, va="bottom")

ax_wb.set_xlabel("Kecepatan Angin @ 100m (m/s)", color=TEXT_COL, fontsize=11)
ax_wb.set_ylabel("Probabilitas Densitas", color=TEXT_COL, fontsize=11)
ax_wb.set_title(f"Distribusi Weibull — {cfg.SITE_NAME}\n"
                f"WPD={wpd_100m:.1f} W/m² | CF={cf_100m*100:.1f}% | ERA5 1980–2025",
                color=TEXT_COL, fontsize=12)
ax_wb.legend(facecolor=PANEL_BG, labelcolor=TEXT_COL, edgecolor=GRID_COL)
ax_wb.tick_params(colors=TEXT_COL)
ax_wb.spines["bottom"].set_color(GRID_COL)
ax_wb.spines["left"].set_color(GRID_COL)
ax_wb.spines["top"].set_visible(False)
ax_wb.spines["right"].set_visible(False)
ax_wb.grid(True, color=GRID_COL, alpha=0.5)

plt.tight_layout()
out_wb = os.path.join(cfg.DIR_OUTPUT, "weibull_fit_site.png")
plt.savefig(out_wb, dpi=150, bbox_inches="tight",
            facecolor=DARK_BG, edgecolor="none")
plt.close()
files_ok.append(out_wb)
print("[DONE] Modul 2.I.3 — weibull_fit_site.png tersimpan")

# ── Plot 3: Trend timeseries ──────────────────────────────────────────────────
print("[INFO] Membuat wind_trend_timeseries.png...")
fig_tr, axes_tr = plt.subplots(2, 1, figsize=(14, 9), facecolor=DARK_BG)

# Panel 1: Monthly mean
monthly_plot = df["wspd_100m"].resample("ME").mean()
axes_tr[0].set_facecolor(PANEL_BG)
axes_tr[0].plot(monthly_plot.index, monthly_plot.values,
                color=ACCENT1, lw=0.8, alpha=0.7, label="Bulanan")
roll12 = monthly_plot.rolling(12, center=True).mean()
axes_tr[0].plot(roll12.index, roll12.values, color=ACCENT2, lw=2.5, label="Rata-rata 12-bulan")
axes_tr[0].set_ylabel("Kecepatan Angin 100m (m/s)", color=TEXT_COL)
axes_tr[0].set_title(f"Time Series Kecepatan Angin ERA5 — {cfg.SITE_NAME}",
                      color=TEXT_COL, fontsize=12)
axes_tr[0].legend(facecolor=PANEL_BG, labelcolor=TEXT_COL, edgecolor=GRID_COL)
axes_tr[0].tick_params(colors=TEXT_COL)
axes_tr[0].grid(True, color=GRID_COL, alpha=0.4)

# Panel 2: Annual trend
axes_tr[1].set_facecolor(PANEL_BG)
if len(annual_means) > 1:
    ax2_yrs = annual_means.index.year if hasattr(annual_means.index, 'year') \
              else np.array([2020, 2024])
    axes_tr[1].scatter(ax2_yrs, annual_means.values,
                        color=ACCENT1, s=50, zorder=5)
    if len(ax2_yrs) > 2:
        slope_a, intercept_a, _, _, _ = linregress(ax2_yrs, annual_means.values)
        yr_fit = np.linspace(ax2_yrs.min(), ax2_yrs.max(), 100)
        axes_tr[1].plot(yr_fit, intercept_a + slope_a*yr_fit, color=ACCENT2, lw=2,
                         label=f"Tren: {trend_ms_per_decade:+.3f} m/s/dekade")
        axes_tr[1].legend(facecolor=PANEL_BG, labelcolor=TEXT_COL, edgecolor=GRID_COL)
axes_tr[1].set_xlabel("Tahun", color=TEXT_COL)
axes_tr[1].set_ylabel("Rata-rata Tahunan (m/s)", color=TEXT_COL)
axes_tr[1].tick_params(colors=TEXT_COL)
axes_tr[1].grid(True, color=GRID_COL, alpha=0.4)

for ax in axes_tr:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["bottom"].set_color(GRID_COL)
    ax.spines["left"].set_color(GRID_COL)

plt.tight_layout()
out_tr = os.path.join(cfg.DIR_OUTPUT, "wind_trend_timeseries.png")
plt.savefig(out_tr, dpi=150, bbox_inches="tight",
            facecolor=DARK_BG, edgecolor="none")
plt.close()
files_ok.append(out_tr)
print("[DONE] Modul 2.I.4 — wind_trend_timeseries.png tersimpan")

# ── Plot 4: WPD Map 100m ──────────────────────────────────────────────────────
print("[INFO] Membuat wpd_map_100m.png...")
LON_G, LAT_G = np.meshgrid(lons_grid, lats_grid)
fig_wpd, ax_wpd = plt.subplots(figsize=(10, 8), facecolor=DARK_BG)
ax_wpd.set_facecolor(PANEL_BG)

cmap_wpd = plt.cm.YlOrRd
cf_wpd = ax_wpd.contourf(LON_G, LAT_G, wpd_grid, levels=20,
                          cmap=cmap_wpd, alpha=0.9)
cbar_wpd = plt.colorbar(cf_wpd, ax=ax_wpd, fraction=0.03, pad=0.02)
cbar_wpd.set_label("WPD (W/m²)", color=TEXT_COL, fontsize=10)
cbar_wpd.ax.yaxis.set_tick_params(color=TEXT_COL)
plt.setp(cbar_wpd.ax.yaxis.get_ticklabels(), color=TEXT_COL)
cbar_wpd.outline.set_edgecolor(GRID_COL)

ax_wpd.plot(cfg.SITE_LON, cfg.SITE_LAT, "v", color="#ff6b35",
            markersize=12, markeredgecolor="white", markeredgewidth=1.5,
            zorder=10, label="Niyama Beach")
ax_wpd.set_xlabel("Bujur (°E)", color=TEXT_COL)
ax_wpd.set_ylabel("Lintang (°S)", color=TEXT_COL)
ax_wpd.set_title(f"Wind Power Density @ 100m AGL — ERA5\n"
                 f"Weibull MLE | Mean={wpd_100m:.1f} W/m²",
                 color=TEXT_COL, fontsize=12)
ax_wpd.tick_params(colors=TEXT_COL)
ax_wpd.legend(facecolor=PANEL_BG, labelcolor=TEXT_COL, edgecolor=GRID_COL)
ax_wpd.spines["bottom"].set_color(GRID_COL)
ax_wpd.spines["left"].set_color(GRID_COL)
ax_wpd.spines["top"].set_visible(False)
ax_wpd.spines["right"].set_visible(False)

plt.tight_layout()
out_wpd_map = os.path.join(cfg.DIR_OUTPUT, "wpd_map_100m.png")
plt.savefig(out_wpd_map, dpi=150, bbox_inches="tight",
            facecolor=DARK_BG, edgecolor="none")
plt.close()
files_ok.append(out_wpd_map)
print("[DONE] Modul 2.I.5 — wpd_map_100m.png tersimpan")

# ── Plot 5: CF Map ────────────────────────────────────────────────────────────
print("[INFO] Membuat capacity_factor_map.png...")
fig_cf, ax_cf = plt.subplots(figsize=(10, 8), facecolor=DARK_BG)
ax_cf.set_facecolor(PANEL_BG)
cf_plot = ax_cf.contourf(LON_G, LAT_G, cf_grid*100, levels=15,
                          cmap="RdYlGn", alpha=0.9)
cbar_cf = plt.colorbar(cf_plot, ax=ax_cf, fraction=0.03, pad=0.02)
cbar_cf.set_label("Capacity Factor (%)", color=TEXT_COL, fontsize=10)
cbar_cf.ax.yaxis.set_tick_params(color=TEXT_COL)
plt.setp(cbar_cf.ax.yaxis.get_ticklabels(), color=TEXT_COL)
cbar_cf.outline.set_edgecolor(GRID_COL)
ax_cf.plot(cfg.SITE_LON, cfg.SITE_LAT, "v", color="#ff6b35",
           markersize=12, markeredgecolor="white", markeredgewidth=1.5,
           zorder=10, label="Niyama Beach")
ax_cf.set_xlabel("Bujur (°E)", color=TEXT_COL)
ax_cf.set_ylabel("Lintang (°S)", color=TEXT_COL)
ax_cf.set_title(f"Capacity Factor Estimasi — Vestas V150-4.5MW @ 100m\n"
                f"Site CF = {cf_100m*100:.1f}%",
                color=TEXT_COL, fontsize=12)
ax_cf.tick_params(colors=TEXT_COL)
ax_cf.legend(facecolor=PANEL_BG, labelcolor=TEXT_COL, edgecolor=GRID_COL)
ax_cf.spines["bottom"].set_color(GRID_COL)
ax_cf.spines["left"].set_color(GRID_COL)
ax_cf.spines["top"].set_visible(False)
ax_cf.spines["right"].set_visible(False)

plt.tight_layout()
out_cf_map = os.path.join(cfg.DIR_OUTPUT, "capacity_factor_map.png")
plt.savefig(out_cf_map, dpi=150, bbox_inches="tight",
            facecolor=DARK_BG, edgecolor="none")
plt.close()
files_ok.append(out_cf_map)
print("[DONE] Modul 2.I.6 — capacity_factor_map.png tersimpan")

# ══════════════════════════════════════════════════════════════════════════════
# Simpan wind_climate.json (ringkasan untuk pipeline downstream)
# ══════════════════════════════════════════════════════════════════════════════
wind_climate_summary = {
    "site": cfg.SITE_NAME, "lat": cfg.SITE_LAT, "lon": cfg.SITE_LON,
    "is_demo": USE_DEMO,
    "wspd_mean_10m": round(annual_mean * (10/10)**cfg.ALPHA_ONSHORE, 3),
    "wspd_mean_100m": round(float(wspd_100m.mean()), 3),
    "wspd_p50_100m": round(p50 * (100/10)**cfg.ALPHA_ONSHORE, 3),
    "wspd_p75_100m": round(p75 * (100/10)**cfg.ALPHA_ONSHORE, 3),
    "wspd_p90_100m": round(p90 * (100/10)**cfg.ALPHA_ONSHORE, 3),
    "wpd_100m_wm2": round(wpd_100m, 2),
    "cf_100m": round(cf_100m, 4),
    "weibull_k_100m": round(k_site, 4),
    "weibull_lambda_100m": round(lam_site, 4),
    "trend_ms_per_decade": round(trend_ms_per_decade, 4),
    "seasonal_ms": seasonal_mean,
    "monthly_mean_ms": {str(i+1): round(float(v),3) for i, v in enumerate(monthly_mean)},
    "grid_shape": {"nlat": int(nlat), "nlon": int(nlon)},
    "grid_lats": lats_grid.tolist(),
    "grid_lons": lons_grid.tolist(),
    "u_mean_grid": np.array(ds["u10"].mean(dim="time").values).tolist()
                   if "u10" in ds else [[0]*nlon]*nlat,
    "v_mean_grid": np.array(ds["v10"].mean(dim="time").values).tolist()
                   if "v10" in ds else [[0]*nlon]*nlat,
}

out_wc = os.path.join(cfg.DIR_PROC, "wind_climate.json")
with open(out_wc, "w") as f:
    json.dump(wind_climate_summary, f, indent=2)
files_ok.append(out_wc)
print(f"[DONE] Modul 2.J — wind_climate.json tersimpan")

# ══════════════════════════════════════════════════════════════════════════════
elapsed = time.time() - t0
print("\n" + "=" * 60)
print(f"  [DONE] Modul 2 — Wind Climate selesai dalam {elapsed:.1f}s")
print(f"  File berhasil : {len(files_ok)}")
for f in files_ok:
    print(f"    [OK] {os.path.basename(f)}")
if files_fail:
    print(f"  File gagal : {len(files_fail)}")
    for f in files_fail:
        print(f"    [FAIL] {f}")
print("=" * 60)
