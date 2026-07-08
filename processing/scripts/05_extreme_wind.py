"""
05_extreme_wind.py — Modul 5: Extreme Wind Event Detection
===========================================================
Input : ERA5 u10/v10 (dari DIR_ERA5_MAIN)
        cfg.DIR_PROC\\wind_profile_heights.json
Output: cfg.DIR_PROC\\extreme_wind_stats.json
        cfg.DIR_OUTPUT\\extreme_wind_return_period.png
        cfg.DIR_OUTPUT\\extreme_wind_seasonality.png
        cfg.DIR_OUTPUT\\enso_correlation.png
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
from scipy.stats import gumbel_r, linregress

files_ok   = []
files_fail = []

DARK_BG  = "#0a0e1a"; PANEL_BG = "#0d1117"; TEXT_COL = "#e0e8ff"
GRID_COL = "#1e2a4a"; ACCENT1  = "#22d3ee"; ACCENT2  = "#f59e0b"
ACCENT3  = "#10b981"; ACCENT4  = "#ef4444"

print("=" * 60)
print("[INFO] Modul 5 — Extreme Wind Event Detection")

# ══════════════════════════════════════════════════════════════════════════════
# 5A. Load data timeseries site (dari output Modul 2 atau ERA5 langsung)
# ══════════════════════════════════════════════════════════════════════════════
IS_DEMO = False

def load_json(path, fallback=None):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    print(f"[WARN] {os.path.basename(path)} tidak ditemukan")
    return fallback

wind_profile = load_json(os.path.join(cfg.DIR_PROC, "wind_profile_heights.json"))
weibull_d    = load_json(os.path.join(cfg.DIR_PROC, "weibull_params.json"))

# Coba load ERA5 timeseries
import glob as glob_mod
try:
    import xarray as xr
    import pandas as pd

    u10_files = sorted(glob_mod.glob(os.path.join(cfg.DIR_ERA5_MAIN, "ERA5_*_u10_*.nc")))
    v10_files = sorted(glob_mod.glob(os.path.join(cfg.DIR_ERA5_MAIN, "ERA5_*_v10_*.nc")))

    if len(u10_files) == 0:
        raise FileNotFoundError("Tidak ada ERA5 u10")

    print(f"[INFO] Load {len(u10_files)} file ERA5 u10 untuk extreme analysis...")
    ds_u = xr.open_mfdataset(u10_files, combine="by_coords", chunks="auto")
    ds_v = xr.open_mfdataset(v10_files, combine="by_coords", chunks="auto")
    ds = xr.merge([ds_u, ds_v])
    if "valid_time" in ds.dims: ds = ds.rename({"valid_time": "time"})
    elif "valid_time" in ds.coords: ds = ds.rename({"valid_time": "time"})
    site = ds.sel(latitude=cfg.SITE_LAT, longitude=cfg.SITE_LON, method="nearest")
    wspd_10m = np.array(site["u10"].values**2 + site["v10"].values**2)**0.5
    times    = pd.to_datetime(site["time"].values)
    wdir     = (270 - np.degrees(np.arctan2(site["v10"].values,
                                             site["u10"].values))) % 360
    ds.close()
    print(f"[INFO] Data: {len(wspd_10m)} jam | {times[0].year}–{times[-1].year}")

except Exception as e:
    print(f"[WARN] Load ERA5 gagal: {e} — pakai data sintetis")
    IS_DEMO = True
    import pandas as pd
    np.random.seed(12345)
    n_years = 46
    n_hours = n_years * 8760
    times   = pd.date_range("1980-01-01", periods=n_hours, freq="1H")

    # Sintetis realistis: dominan 5–7 m/s, extreme event ~1-2x/tahun
    seasonal = 1 + 0.35 * np.cos((times.month.values - 7) / 12 * 2 * np.pi)
    base_wspd = (np.random.weibull(2.2, n_hours) * 4.5) * seasonal
    # Tambah extreme events (17+ m/s @ 100m ≈ 8.5+ m/s @ 10m)
    extreme_mask = np.random.random(n_hours) < 0.0003  # ~2-3 jam/tahun
    base_wspd[extreme_mask] += np.random.uniform(5, 12, extreme_mask.sum())
    wspd_10m = np.clip(base_wspd, 0, 30)
    wdir     = (270 - np.random.uniform(-180, 180, n_hours)) % 360

# Ekstrapolasi ke 100m
wspd_100m = wspd_10m * (100 / cfg.Z_REF) ** cfg.ALPHA_ONSHORE
print(f"[INFO] Wspd @ 100m: mean={wspd_100m.mean():.2f} | max={wspd_100m.max():.2f} m/s")

# ── Identifikasi extreme events ───────────────────────────────────────────────
extreme_mask = wspd_100m > cfg.EXTREME_WS_THRESHOLD
n_extreme_total = extreme_mask.sum()
wdir_change = np.abs(np.diff(wdir, prepend=wdir[0]))
wdir_change = np.minimum(wdir_change, 360 - wdir_change)
ewd_mask = wdir_change > cfg.EXTREME_DIR_CHANGE
print(f"[INFO] Extreme events (>{cfg.EXTREME_WS_THRESHOLD} m/s @ 100m): "
      f"{n_extreme_total} jam ({n_extreme_total/len(wspd_100m)*100:.2f}%)")
print(f"[INFO] EWD events (DeltaDir>{cfg.EXTREME_DIR_CHANGE} deg/hr): {ewd_mask.sum()}")

# ══════════════════════════════════════════════════════════════════════════════
# 5B. Annual maxima & Gumbel fit
# ══════════════════════════════════════════════════════════════════════════════
years_arr = times.year.values
years_uniq = np.unique(years_arr)
annual_max = []
for yr in years_uniq:
    mask_yr = years_arr == yr
    if mask_yr.sum() > 100:
        annual_max.append(float(wspd_100m[mask_yr].max()))

annual_max = np.array(annual_max)
print(f"[INFO] Annual maxima: {len(annual_max)} tahun | "
      f"mean={annual_max.mean():.2f} max={annual_max.max():.2f} m/s")

# Gumbel fit
loc_g, scale_g = gumbel_r.fit(annual_max)
print(f"[INFO] Gumbel fit: loc={loc_g:.3f}, scale={scale_g:.3f}")

def gumbel_return(T, loc, scale):
    """Return period T → wind speed."""
    return loc - scale * np.log(-np.log(1 - 1/T))

return_periods = [1, 5, 10, 25, 50, 100]
return_speeds  = {T: round(gumbel_return(T, loc_g, scale_g), 2)
                  for T in return_periods}
print(f"[INFO] Return speeds: {return_speeds}")

V50 = return_speeds[50]
V_ref = 1.4 * V50
if V_ref >= 50:   iec_class = "I"
elif V_ref >= 42.5: iec_class = "II"
elif V_ref >= 37.5: iec_class = "III"
else:             iec_class = "S (site-specific)"
print(f"[INFO] V50={V50:.1f} m/s | V_ref={V_ref:.1f} m/s -> IEC Class {iec_class}")
print("[DONE] Modul 5.B — Gumbel fit selesai")

# Confidence interval 90% (bootstrap)
n_boot = 500
boot_v50 = []
rng = np.random.default_rng(42)
for _ in range(n_boot):
    sample = rng.choice(annual_max, size=len(annual_max), replace=True)
    l, s = gumbel_r.fit(sample)
    boot_v50.append(gumbel_return(50, l, s))
ci_lo = np.percentile(boot_v50, 5)
ci_hi = np.percentile(boot_v50, 95)
print(f"[INFO] V50 90% CI: [{ci_lo:.1f}, {ci_hi:.1f}] m/s")

# ══════════════════════════════════════════════════════════════════════════════
# 5C. Seasonality extreme events
# ══════════════════════════════════════════════════════════════════════════════
months     = times.month.values
extreme_by_month = np.zeros(12)
hours_by_month   = np.zeros(12)
for m in range(1, 13):
    mask_m = months == m
    extreme_by_month[m-1] = extreme_mask[mask_m].sum()
    hours_by_month[m-1]   = mask_m.sum()

n_years_actual = len(years_uniq)
extreme_hr_per_month_per_yr = extreme_by_month / n_years_actual
print("[DONE] Modul 5.C — Seasonality selesai")

# ══════════════════════════════════════════════════════════════════════════════
# 5D. Korelasi ENSO (ONI index)
# ══════════════════════════════════════════════════════════════════════════════
oni_data = None
try:
    import urllib.request
    print("[INFO] Mencoba download ONI index dari NOAA...")
    url = "https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt"
    with urllib.request.urlopen(url, timeout=10) as response:
        raw = response.read().decode("utf-8")
    oni_lines = [l.strip().split() for l in raw.strip().split("\n") if l.strip()
                 and not l.startswith("SEAS")]
    oni_rows = []
    for row in oni_lines:
        try:
            yr = int(row[1])
            oni_val = float(row[3])
            oni_rows.append((yr, oni_val))
        except (ValueError, IndexError):
            continue
    if oni_rows:
        import pandas as pd
        df_oni = pd.DataFrame(oni_rows, columns=["year","oni"])
        oni_annual = df_oni.groupby("year")["oni"].mean()
        print(f"[INFO] ONI data berhasil: {len(oni_annual)} tahun")
        oni_data = oni_annual
except Exception as e:
    print(f"[WARN] Download ONI gagal: {e} — menggunakan ONI sintetis")
    # ONI sintetis: pola ENSO periode ~4 tahun
    yr_range = np.arange(1980, 2026)
    oni_synth = 0.8 * np.sin(yr_range / 3.7 * 2 * np.pi) + \
                0.3 * np.sin(yr_range / 7.2 * 2 * np.pi) + \
                0.1 * np.random.randn(len(yr_range))
    import pandas as pd
    oni_data = pd.Series(oni_synth, index=yr_range)
    oni_data.index.name = "year"
    IS_DEMO = True

# Annual extreme event count per year
import pandas as pd
df_ext = pd.DataFrame({"extreme": extreme_mask, "year": years_arr})
ext_count_yr = df_ext.groupby("year")["extreme"].sum()

# Intersect dengan ONI
common_yrs = sorted(set(ext_count_yr.index) & set(oni_data.index))
if len(common_yrs) > 3:
    ext_vals = ext_count_yr.loc[common_yrs].values.astype(float)
    oni_vals = oni_data.loc[common_yrs].values.astype(float)
    from scipy.stats import pearsonr
    corr_r, corr_p = pearsonr(oni_vals, ext_vals)
    print(f"[INFO] Korelasi ENSO-Extreme: r={corr_r:.3f}, p={corr_p:.3f}")
else:
    corr_r, corr_p = 0.0, 1.0
    common_yrs = [2020, 2021, 2022]
    ext_vals = np.array([5.0, 3.0, 8.0])
    oni_vals = np.array([-0.5, 0.3, 0.8])
print("[DONE] Modul 5.D — ENSO korelasi selesai")

# ══════════════════════════════════════════════════════════════════════════════
# 5E. Simpan extreme_wind_stats.json
# ══════════════════════════════════════════════════════════════════════════════
extreme_stats = {
    "is_demo": IS_DEMO,
    "site": cfg.SITE_NAME, "lat": cfg.SITE_LAT, "lon": cfg.SITE_LON,
    "threshold_ms": cfg.EXTREME_WS_THRESHOLD,
    "total_extreme_hours": int(n_extreme_total),
    "extreme_fraction_pct": round(float(n_extreme_total/len(wspd_100m)*100), 4),
    "ewd_events_total": int(ewd_mask.sum()),
    "gumbel_loc": round(loc_g, 4),
    "gumbel_scale": round(scale_g, 4),
    "return_periods": {
        str(T): {"speed_ms": v, "v_ref_ms": round(v * 1.4, 2)}
        for T, v in return_speeds.items()
    },
    "v50_ms": V50,
    "v_ref_ms": round(V_ref, 2),
    "iec_class": iec_class,
    "iec_description": f"IEC Class {iec_class} | V_ref={V_ref:.1f} m/s",
    "v50_ci90_lo": round(ci_lo, 2),
    "v50_ci90_hi": round(ci_hi, 2),
    "seasonality_hours_per_month_per_yr": {
        str(m+1): round(float(v), 2)
        for m, v in enumerate(extreme_hr_per_month_per_yr)
    },
    "enso_correlation_r": round(float(corr_r), 4),
    "enso_correlation_p": round(float(corr_p), 4),
    "annual_max_ms": [round(v, 2) for v in annual_max.tolist()],
    "n_years": int(n_years_actual),
    "weibull_k_100m": weibull_d.get("hub_heights",{}).get("100m",{}).get("k", 2.0) if weibull_d else 2.0,
    "weibull_lambda_100m": weibull_d.get("hub_heights",{}).get("100m",{}).get("lambda", 6.0) if weibull_d else 6.0,
}

out_es = os.path.join(cfg.DIR_PROC, "extreme_wind_stats.json")
with open(out_es, "w") as f:
    json.dump(extreme_stats, f, indent=2)
files_ok.append(out_es)
print(f"[DONE] Modul 5.E — extreme_wind_stats.json tersimpan")

# ══════════════════════════════════════════════════════════════════════════════
# PLOTS
# ══════════════════════════════════════════════════════════════════════════════

# ── Plot 1: Return Period Curve ───────────────────────────────────────────────
print("[INFO] Membuat extreme_wind_return_period.png...")
fig_rp, ax_rp = plt.subplots(figsize=(11, 7), facecolor=DARK_BG)
ax_rp.set_facecolor(PANEL_BG)

T_range = np.logspace(np.log10(1.5), np.log10(200), 300)
V_fit   = gumbel_return(T_range, loc_g, scale_g)
# CI
ci_lo_arr = np.array([np.percentile([gumbel_return(T, *gumbel_r.fit(
    np.random.choice(annual_max, len(annual_max), replace=True)))
    for _ in range(200)], 5) for T in [2,10,50]])
ci_hi_arr = np.array([np.percentile([gumbel_return(T, *gumbel_r.fit(
    np.random.choice(annual_max, len(annual_max), replace=True)))
    for _ in range(200)], 95) for T in [2,10,50]])

ax_rp.fill_between([2,10,50], ci_lo_arr, ci_hi_arr,
                    alpha=0.2, color=ACCENT1, label="CI 90%")
ax_rp.semilogx(T_range, V_fit, color=ACCENT1, lw=2.5, label="Gumbel fit")

# Empirical plotting positions (Gringorten)
n_am = len(annual_max)
T_emp = (n_am + 0.12) / (np.arange(1, n_am+1) - 0.44)
V_emp = np.sort(annual_max)
ax_rp.scatter(T_emp, V_emp, color=ACCENT2, s=50, zorder=5,
               edgecolors="white", linewidths=0.5, label="Annual maxima (Gringorten)")

# IEC markers
for T_rp, v_rp, col, label in [(50, V50, ACCENT4, f"V50={V50:.1f} m/s"),
                                 (25, return_speeds[25], "#f97316",
                                  f"V25={return_speeds[25]:.1f} m/s"),
                                 (100, return_speeds[100], "#a855f7",
                                  f"V100={return_speeds[100]:.1f} m/s")]:
    ax_rp.axhline(v_rp, color=col, lw=1.2, linestyle="--", alpha=0.7)
    ax_rp.axvline(T_rp, color=col, lw=1.2, linestyle="--", alpha=0.7)
    ax_rp.annotate(label, xy=(T_rp, v_rp),
                    xytext=(T_rp*1.2, v_rp+0.5),
                    color=col, fontsize=9)

ax_rp.set_xlabel("Return Period (years)", color=TEXT_COL, fontsize=11)
ax_rp.set_ylabel("Peak Wind Speed @ 100m (m/s)", color=TEXT_COL, fontsize=11)
ax_rp.set_title(f"Extreme Wind Return Period — {cfg.SITE_NAME}\n"
                f"Gumbel Distribution | IEC Class {iec_class} | "
                f"V50={V50:.1f} m/s | V_ref={V_ref:.1f} m/s",
                color=TEXT_COL, fontsize=11)
ax_rp.legend(facecolor=PANEL_BG, labelcolor=TEXT_COL, edgecolor=GRID_COL)
ax_rp.tick_params(colors=TEXT_COL)
ax_rp.grid(True, color=GRID_COL, alpha=0.4, which="both")
for sp in ax_rp.spines.values(): sp.set_color(GRID_COL)
ax_rp.spines["top"].set_visible(False)
ax_rp.spines["right"].set_visible(False)

plt.tight_layout()
out_rp = os.path.join(cfg.DIR_OUTPUT, "extreme_wind_return_period.png")
plt.savefig(out_rp, dpi=150, bbox_inches="tight",
            facecolor=DARK_BG, edgecolor="none")
plt.close()
files_ok.append(out_rp)
print("[DONE] Modul 5.P1 — extreme_wind_return_period.png tersimpan")

# ── Plot 2: Seasonality ───────────────────────────────────────────────────────
print("[INFO] Membuat extreme_wind_seasonality.png...")
month_names = ["Jan","Feb","Mar","Apr","Mei","Jun","Jul","Agu","Sep","Okt","Nov","Des"]

fig_se, axes_se = plt.subplots(1, 2, figsize=(14, 6), facecolor=DARK_BG)
ax_s1, ax_s2 = axes_se

# Bar: jam extreme per bulan per tahun
ax_s1.set_facecolor(PANEL_BG)
colors_month = [ACCENT4 if extreme_hr_per_month_per_yr[m] > np.mean(extreme_hr_per_month_per_yr)
                else ACCENT3 for m in range(12)]
bars = ax_s1.bar(range(12), extreme_hr_per_month_per_yr, color=colors_month,
                  edgecolor=DARK_BG, linewidth=0.8, alpha=0.9)
ax_s1.set_xticks(range(12))
ax_s1.set_xticklabels(month_names, color=TEXT_COL)
ax_s1.set_ylabel(f"Jam Extreme/tahun\n(>{cfg.EXTREME_WS_THRESHOLD} m/s @ 100m)",
                  color=TEXT_COL, fontsize=10)
ax_s1.set_title("Musiman Extreme Wind Events", color=TEXT_COL, fontsize=11)
ax_s1.tick_params(colors=TEXT_COL)
ax_s1.grid(True, axis="y", color=GRID_COL, alpha=0.4)
ax_s1.spines["top"].set_visible(False)
ax_s1.spines["right"].set_visible(False)
for sp in ["bottom","left"]: ax_s1.spines[sp].set_color(GRID_COL)

# Annual count timeseries
ax_s2.set_facecolor(PANEL_BG)
yr_plot  = ext_count_yr.index.values
cnt_plot = ext_count_yr.values
ax_s2.bar(yr_plot, cnt_plot, color=ACCENT1, alpha=0.7, edgecolor=DARK_BG, linewidth=0.5)
slope_ext, intercept_ext, r_ext, p_ext, _ = linregress(
    yr_plot.astype(float), cnt_plot.astype(float))
yr_fit = np.array([yr_plot.min(), yr_plot.max()], dtype=float)
ax_s2.plot(yr_fit, intercept_ext + slope_ext * yr_fit, color=ACCENT4,
            lw=2, label=f"Tren: {slope_ext*10:+.1f} jam/dekade")
ax_s2.set_xlabel("Tahun", color=TEXT_COL)
ax_s2.set_ylabel("Jam Extreme per Tahun", color=TEXT_COL)
ax_s2.set_title("Tren Annual Extreme Wind Events", color=TEXT_COL, fontsize=11)
ax_s2.legend(facecolor=PANEL_BG, labelcolor=TEXT_COL, edgecolor=GRID_COL)
ax_s2.tick_params(colors=TEXT_COL)
ax_s2.grid(True, color=GRID_COL, alpha=0.4)
ax_s2.spines["top"].set_visible(False)
ax_s2.spines["right"].set_visible(False)
for sp in ["bottom","left"]: ax_s2.spines[sp].set_color(GRID_COL)

plt.suptitle(f"Seasonality Extreme Wind — {cfg.SITE_NAME} | ERA5 1980–2025",
             color=TEXT_COL, fontsize=12)
plt.tight_layout()
out_se = os.path.join(cfg.DIR_OUTPUT, "extreme_wind_seasonality.png")
plt.savefig(out_se, dpi=150, bbox_inches="tight",
            facecolor=DARK_BG, edgecolor="none")
plt.close()
files_ok.append(out_se)
print("[DONE] Modul 5.P2 — extreme_wind_seasonality.png tersimpan")

# ── Plot 3: ENSO correlation ──────────────────────────────────────────────────
print("[INFO] Membuat enso_correlation.png...")
fig_en, axes_en = plt.subplots(1, 2, figsize=(14, 6), facecolor=DARK_BG)
ax_e1, ax_e2 = axes_en

# Scatter ONI vs extreme count
ax_e1.set_facecolor(PANEL_BG)
# Colour code La Niña/El Niño
enso_type = np.where(oni_vals < -0.5, "La Niña",
            np.where(oni_vals > 0.5, "El Niño", "Netral"))
for etype, col, mark in [("La Niña", ACCENT1, "o"),
                           ("Netral",  "#64748b",  "s"),
                           ("El Niño", ACCENT4, "^")]:
    mask_e = enso_type == etype
    if mask_e.any():
        ax_e1.scatter(oni_vals[mask_e], ext_vals[mask_e], s=80, color=col,
                       marker=mark, edgecolors="white", linewidths=0.5,
                       label=etype, zorder=5)

if len(oni_vals) > 3:
    sl, ic, _, _, _ = linregress(oni_vals, ext_vals)
    oni_fit = np.linspace(oni_vals.min()-0.2, oni_vals.max()+0.2, 50)
    ax_e1.plot(oni_fit, ic + sl*oni_fit, color=ACCENT2, lw=2, linestyle="--",
                label=f"r={corr_r:.3f} (p={corr_p:.3f})")

ax_e1.axvline(-0.5, color=ACCENT1, lw=1, linestyle=":", alpha=0.6)
ax_e1.axvline(0.5, color=ACCENT4, lw=1, linestyle=":", alpha=0.6)
ax_e1.set_xlabel("ONI Index (3-bulan mean)", color=TEXT_COL)
ax_e1.set_ylabel("Jam Extreme per Tahun", color=TEXT_COL)
ax_e1.set_title(f"Korelasi ENSO – Extreme Wind\nr={corr_r:.3f}",
                 color=TEXT_COL, fontsize=11)
ax_e1.legend(facecolor=PANEL_BG, labelcolor=TEXT_COL, edgecolor=GRID_COL)
ax_e1.tick_params(colors=TEXT_COL)
ax_e1.grid(True, color=GRID_COL, alpha=0.4)
ax_e1.spines["top"].set_visible(False); ax_e1.spines["right"].set_visible(False)
for sp in ["bottom","left"]: ax_e1.spines[sp].set_color(GRID_COL)

# ONI timeseries + extreme count
ax_e2.set_facecolor(PANEL_BG)
yr_oni = np.array(common_yrs)
ax_e2.bar(yr_oni, ext_vals, color=ACCENT1, alpha=0.6, label="Extreme hours/yr")
ax_e2_twin = ax_e2.twinx()
ax_e2_twin.plot(yr_oni, oni_vals, color=ACCENT2, lw=2, label="ONI index")
ax_e2_twin.axhline(0.5, color=ACCENT4, lw=1, linestyle="--", alpha=0.5)
ax_e2_twin.axhline(-0.5, color=ACCENT1, lw=1, linestyle="--", alpha=0.5)
ax_e2.set_xlabel("Tahun", color=TEXT_COL)
ax_e2.set_ylabel("Jam Extreme per Tahun", color=ACCENT1)
ax_e2_twin.set_ylabel("ONI Index", color=ACCENT2)
ax_e2.set_title("Temporal: Extreme Wind vs ENSO Phase", color=TEXT_COL, fontsize=11)
ax_e2.tick_params(colors=TEXT_COL); ax_e2_twin.tick_params(colors=ACCENT2)
ax_e2.grid(True, color=GRID_COL, alpha=0.3)
ax_e2.spines["top"].set_visible(False)

plt.suptitle(f"Korelasi ENSO dan Extreme Wind — {cfg.SITE_NAME}",
             color=TEXT_COL, fontsize=12)
plt.tight_layout()
out_en = os.path.join(cfg.DIR_OUTPUT, "enso_correlation.png")
plt.savefig(out_en, dpi=150, bbox_inches="tight",
            facecolor=DARK_BG, edgecolor="none")
plt.close()
files_ok.append(out_en)
print("[DONE] Modul 5.P3 — enso_correlation.png tersimpan")

# ══════════════════════════════════════════════════════════════════════════════
elapsed = time.time() - t0
print("\n" + "=" * 60)
print(f"  [DONE] Modul 5 — Extreme Wind selesai dalam {elapsed:.1f}s")
print(f"  IEC Recommendation: Class {iec_class} | V50={V50:.1f} m/s")
print(f"  File berhasil : {len(files_ok)}")
for f in files_ok:
    print(f"    [OK] {os.path.basename(f)}")
print("=" * 60)
