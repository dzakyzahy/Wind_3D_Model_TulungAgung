"""
04_wake_analysis.py — Modul 4: Wake Effect Analysis (Jensen/Park Model)
=======================================================================
Input : cfg.DIR_PROC\\wind_corrected_3km.json
        cfg.DIR_PROC\\weibull_params.json
        cfg.DIR_PROC\\terrain_stats.json
Output: cfg.DIR_PROC\\wake_results.json
        cfg.DIR_OUTPUT\\wake_layout_comparison.png
        cfg.DIR_OUTPUT\\wake_loss_per_turbine.png
        cfg.DIR_OUTPUT\\aep_vs_spacing.png
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
import matplotlib.patches as mpatches

files_ok   = []
files_fail = []

DARK_BG  = "#0a0e1a"
PANEL_BG = "#0d1117"
TEXT_COL = "#e0e8ff"
GRID_COL = "#1e2a4a"
ACCENT1  = "#22d3ee"
ACCENT2  = "#f59e0b"
ACCENT3  = "#10b981"
ACCENT4  = "#ef4444"

print("=" * 60)
print("[INFO] Modul 4 — Wake Effect Analysis")

# ══════════════════════════════════════════════════════════════════════════════
# Helper: load JSON dengan fallback
# ══════════════════════════════════════════════════════════════════════════════
def load_json(path, fallback=None):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    print(f"[WARN] {os.path.basename(path)} tidak ditemukan")
    return fallback

wind_corr   = load_json(os.path.join(cfg.DIR_PROC, "wind_corrected_3km.json"))
weibull_d   = load_json(os.path.join(cfg.DIR_PROC, "weibull_params.json"))
terrain_s   = load_json(os.path.join(cfg.DIR_PROC, "terrain_stats.json"))
wind_data_j = load_json(os.path.join(cfg.DIR_PROC, "wind_data.json"))

IS_DEMO = (wind_corr is None or weibull_d is None)

# ── Weibull params @ 100m ─────────────────────────────────────────────────────
if weibull_d:
    k_100   = weibull_d.get("hub_heights",{}).get("100m",{}).get("k", 2.0)
    lam_100 = weibull_d.get("hub_heights",{}).get("100m",{}).get("lambda", 6.0)
    # Wind rose: frekuensi per arah dari data sektor
    seasonal = weibull_d.get("seasonal_mean_ms", {"DJF":4.5,"MAM":4.0,"JJA":5.5,"SON":4.8})
else:
    k_100 = 2.0; lam_100 = 6.0
    seasonal = {"DJF":4.5,"MAM":4.0,"JJA":5.5,"SON":4.8}
    IS_DEMO = True

# ── WPD grid untuk identifikasi zona kandidat ────────────────────────────────
if wind_data_j:
    # Coba ambil dari wind_data.json
    try:
        nx_w = wind_data_j["meta"]["nx"]
        nz_w = wind_data_j["meta"]["nz"]
        # Layer 100m (index 1 jika ada)
        lyr = wind_data_j["wind_layers"][1] if len(wind_data_j["wind_layers"]) > 1 \
              else wind_data_j["wind_layers"][0]
        wpd_flat = np.array(lyr.get("wpd", []), dtype=float)
        wspd_flat = np.array(lyr.get("wspd", []), dtype=float)
        if wpd_flat.size == nx_w * nz_w:
            wpd_grid  = wpd_flat.reshape(nz_w, nx_w)
            wspd_grid = wspd_flat.reshape(nz_w, nx_w)
        else:
            raise ValueError("Shape mismatch")
        dem_norm = np.array(wind_data_j.get("terrain", []), dtype=float)
        dem_elev = np.array(wind_data_j.get("elevation_m",
                            np.zeros((nz_w, nx_w))), dtype=float)
        if dem_norm.ndim == 1:
            dem_norm = dem_norm.reshape(nz_w, nx_w)
        if dem_elev.ndim == 1:
            dem_elev = dem_elev.reshape(nz_w, nx_w)
    except Exception as e:
        print(f"[WARN] Parse wind_data.json gagal: {e} — pakai dummy grid")
        nx_w = nz_w = 60
        wpd_grid  = np.random.uniform(50, 400, (nz_w, nx_w))
        wspd_grid = np.sqrt(2 * wpd_grid / (0.5 * cfg.RHO_AIR * np.pi * 1))**(1/3)
        dem_elev  = np.zeros((nz_w, nx_w))
        IS_DEMO   = True
else:
    nx_w = nz_w = 60
    wpd_grid  = np.random.uniform(80, 350, (nz_w, nx_w))
    wspd_grid = np.full((nz_w, nx_w), lam_100 * 0.8862)
    dem_elev  = np.zeros((nz_w, nx_w))
    IS_DEMO   = True

# ── Slope constraint ─────────────────────────────────────────────────────────
grad_y, grad_x = np.gradient(dem_elev)
pix_km = max(1, (cfg.LON_MAX - cfg.LON_MIN) * 111 / nx_w)
slope_deg = np.degrees(np.arctan(np.sqrt(grad_x**2 + grad_y**2) / (pix_km * 1000)))

print(f"[INFO] WPD grid: {wpd_grid.shape} | mean={wpd_grid.mean():.1f} W/m²")

# ══════════════════════════════════════════════════════════════════════════════
# 4A. Identifikasi zona WPD tertinggi
# ══════════════════════════════════════════════════════════════════════════════
valid_mask = (slope_deg <= 30) & (dem_elev >= 10)
wpd_masked = np.where(valid_mask, wpd_grid, 0)
valid_vals = wpd_masked[(wpd_masked > 0) & (~np.isnan(wpd_masked))]
if len(valid_vals) > 0:
    threshold = np.percentile(valid_vals, 90)
else:
    threshold = np.nanmean(wpd_grid) if not np.all(np.isnan(wpd_grid)) else 100.0
top_zone   = wpd_masked >= threshold

# Centroid zona terbaik
if top_zone.any():
    rows, cols = np.where(top_zone)
    center_row = int(rows.mean())
    center_col = int(cols.mean())
else:
    center_row = nz_w // 3
    center_col = nx_w // 2

# Koordinat pusat farm
center_lat = cfg.LAT_MAX - (center_row / nz_w) * (cfg.LAT_MAX - cfg.LAT_MIN)
center_lon = cfg.LON_MIN + (center_col / nx_w) * (cfg.LON_MAX - cfg.LON_MIN)
print(f"[INFO] Zona WPD terbaik: ({center_lat:.3f}, {center_lon:.3f}) | "
      f"WPD threshold={threshold:.1f} W/m²")
print("[DONE] Modul 4.A — Identifikasi zona WPD selesai")

# ══════════════════════════════════════════════════════════════════════════════
# Power curve interpolation
# ══════════════════════════════════════════════════════════════════════════════
pc_ws  = np.array(sorted(cfg.POWER_CURVE.keys()), dtype=float)
pc_kw  = np.array([cfg.POWER_CURVE[v] for v in sorted(cfg.POWER_CURVE.keys())], dtype=float)

def power_from_ws(ws):
    return np.interp(np.maximum(0, ws), pc_ws, pc_kw)

def weibull_pdf(u, k, lam):
    u = np.maximum(u, 1e-6)
    return (k/lam) * (u/lam)**(k-1) * np.exp(-(u/lam)**k)

def calc_aep_single(ws_free, k=k_100, lam=lam_100):
    """AEP per turbin (kWh/yr) dari kecepatan freestream."""
    u_r = np.linspace(0, 30, 2000)
    pdf = weibull_pdf(u_r, k, lam * (ws_free / max(lam*0.8862, 0.1)))
    p_u = power_from_ws(u_r)
    return float(np.trapz(pdf * p_u, u_r) * 8760)

# ══════════════════════════════════════════════════════════════════════════════
# 4C. Jensen wake model
# ══════════════════════════════════════════════════════════════════════════════
def jensen_wake(U_inf, x, r0, Ct, k_wake):
    """Velocity deficit downstream."""
    if x <= 0:
        return U_inf
    deficit = (1 - np.sqrt(1 - Ct)) * (r0 / (r0 + k_wake * x))**2
    return U_inf * (1 - deficit)

def calc_wake_field(turbine_xy, U_inf, wind_dir_deg, r0, Ct, k_wake):
    """
    turbine_xy: array (N,2) posisi turbin dalam meter
    U_inf     : kecepatan freestream m/s
    wind_dir_deg: arah angin (meteorologi) dalam derajat
    Retuns: array (N,) kecepatan efektif per turbin
    """
    N = len(turbine_xy)
    # Rotasi ke frame angin (x searah angin)
    theta = np.deg2rad(270 - wind_dir_deg)   # konversi met→math
    cos_t, sin_t = np.cos(theta), np.sin(theta)

    # Posisi dalam frame angin
    pos_rot = np.column_stack([
        turbine_xy[:,0]*cos_t + turbine_xy[:,1]*sin_t,
        -turbine_xy[:,0]*sin_t + turbine_xy[:,1]*cos_t
    ])

    U_eff = np.full(N, U_inf)
    for i in range(N):
        deficits_sq = 0.0
        for j in range(N):
            if i == j: continue
            dx = pos_rot[i,0] - pos_rot[j,0]   # jarak downstream dari j
            if dx <= 0: continue                  # tidak di downstream
            dy = abs(pos_rot[i,1] - pos_rot[j,1])  # offset lateral
            # Radius wake di posisi i
            r_wake = r0 + k_wake * dx
            if dy > r_wake: continue             # di luar cone
            deficit = (1 - np.sqrt(1 - Ct)) * (r0 / r_wake)**2
            deficits_sq += deficit**2
        U_eff[i] = U_inf * (1 - np.sqrt(deficits_sq))
    return U_eff

# ══════════════════════════════════════════════════════════════════════════════
# 4B. Definisi layout (koordinat dalam meter dari pusat farm)
# ══════════════════════════════════════════════════════════════════════════════
D = cfg.ROTOR_DIAMETER  # 150m
r0 = D / 2              # 75m

def make_grid_layout(nx_t, ny_t, spacing_m, rotation_deg=0):
    """Grid layout dengan rotasi opsional."""
    positions = []
    for iy in range(ny_t):
        for ix in range(nx_t):
            x = (ix - (nx_t-1)/2) * spacing_m
            y = (iy - (ny_t-1)/2) * spacing_m
            theta = np.deg2rad(rotation_deg)
            xr = x*np.cos(theta) - y*np.sin(theta)
            yr = x*np.sin(theta) + y*np.cos(theta)
            positions.append([xr, yr])
    return np.array(positions)

def make_ridge_layout(n_t, spacing_m, ridge_azimuth=60):
    """Layout sepanjang ridge (azimuth dari utara, derajat)."""
    positions = []
    for i in range(n_t):
        dist = (i - (n_t-1)/2) * spacing_m
        theta = np.deg2rad(90 - ridge_azimuth)
        positions.append([dist * np.cos(theta), dist * np.sin(theta)])
    return np.array(positions)

# Ridge azimuth dari terrain stats
if terrain_s and terrain_s.get("ridge_coords"):
    rc = terrain_s["ridge_coords"]
    if len(rc) > 5:
        lats_r = [p[0] for p in rc[:20]]
        lons_r = [p[1] for p in rc[:20]]
        dy = np.mean(np.diff(lats_r)) * 111000
        dx = np.mean(np.diff(lons_r)) * 111000 * np.cos(np.deg2rad(cfg.SITE_LAT))
        ridge_az = (90 - np.degrees(np.arctan2(dy, dx))) % 360
    else:
        ridge_az = 70  # default: NE–SW
else:
    ridge_az = 70

layouts = {
    "A_grid_7D": {
        "positions": make_grid_layout(5, 5, 7*D),
        "label": "Grid 5×5 @ 7D (1050m)",
        "color": ACCENT1,
    },
    "B_grid_10D": {
        "positions": make_grid_layout(5, 5, 10*D),
        "label": "Grid 5×5 @ 10D (1500m)",
        "color": ACCENT3,
    },
    "C_ridge": {
        "positions": make_ridge_layout(25, 8*D, ridge_azimuth=ridge_az),
        "label": f"Ridge @ 8D (1200m) az={ridge_az:.0f}°",
        "color": ACCENT2,
    },
}

print("[DONE] Modul 4.B — Layout kandidat selesai")

# ══════════════════════════════════════════════════════════════════════════════
# 4D. Hitung AEP per layout
# ══════════════════════════════════════════════════════════════════════════════
# Frekuensi arah angin: distribusi sederhana berbasis Jawa bagian selatan
# (dominan E–SE pada musim timur, W–NW musim barat)
dir_freq = {}
n_sectors = 36
for i in range(n_sectors):
    deg = i * 10
    # Dominan 100-120° (E-SE) dan 250-280° (W-WSW)
    f = (0.5 * np.exp(-((deg - 110)**2) / (2*30**2)) +
         0.3 * np.exp(-((deg - 265)**2) / (2*25**2)) +
         0.1 * np.exp(-((deg - 180)**2) / (2*40**2)))
    dir_freq[deg] = f

total_freq = sum(dir_freq.values())
for k in dir_freq:
    dir_freq[k] /= total_freq

# U_inf @ 100m (mean dari Weibull)
U_inf_mean = lam_100 * 0.8862   # Weibull mean

results = {}
for name, layout in layouts.items():
    pos = layout["positions"]
    N   = len(pos)
    farm_area_km2 = max(1, (pos[:,0].max()-pos[:,0].min())
                        * (pos[:,1].max()-pos[:,1].min()) / 1e6)

    # AEP tanpa wake
    aep_no_wake = N * calc_aep_single(U_inf_mean)

    # AEP dengan wake — sum per arah angin
    aep_wake_kwh = 0.0
    for dir_deg, freq in dir_freq.items():
        U_eff = calc_wake_field(pos, U_inf_mean, dir_deg,
                                r0, cfg.CT, cfg.WAKE_K_ONSHORE)
        aep_dir = sum(calc_aep_single(float(u)) for u in U_eff)
        aep_wake_kwh += freq * aep_dir

    wake_loss_pct = 100 * (aep_no_wake - aep_wake_kwh) / max(aep_no_wake, 1)
    efficiency    = 100 - wake_loss_pct
    aep_gwh       = aep_wake_kwh / 1e6  # MWh → GWh

    results[name] = {
        "label": layout["label"], "n_turbines": N,
        "aep_gwh":       round(aep_gwh, 2),
        "aep_no_wake_gwh": round(aep_no_wake / 1e6, 2),
        "wake_loss_pct": round(wake_loss_pct, 2),
        "farm_area_km2": round(farm_area_km2, 2),
        "efficiency_pct": round(efficiency, 2),
        "positions_m":   pos.tolist(),
    }
    print(f"[INFO] {name}: AEP={aep_gwh:.2f} GWh/yr | Wake loss={wake_loss_pct:.1f}% | "
          f"η={efficiency:.1f}%")

# Optimal layout
best = min(results, key=lambda k: results[k]["wake_loss_pct"])
print(f"[INFO] Layout terbaik: {best} (wake loss={results[best]['wake_loss_pct']:.1f}%)")
print("[DONE] Modul 4.D — AEP dihitung")

# ══════════════════════════════════════════════════════════════════════════════
# 4E. Sensitivity: AEP vs spacing (5D–15D)
# ══════════════════════════════════════════════════════════════════════════════
print("[INFO] Menghitung sensitivity spacing 5D–15D...")
spacings_D  = list(range(5, 16))
aep_spacing = []
area_spacing = []

for sp_D in spacings_D:
    pos_sp = make_grid_layout(5, 5, sp_D * D)
    area_sp = ((pos_sp[:,0].max()-pos_sp[:,0].min())
               * (pos_sp[:,1].max()-pos_sp[:,1].min()) / 1e6)
    aep_sp = 0.0
    for dir_deg, freq in dir_freq.items():
        U_eff = calc_wake_field(pos_sp, U_inf_mean, dir_deg,
                                r0, cfg.CT, cfg.WAKE_K_ONSHORE)
        aep_sp += freq * sum(calc_aep_single(float(u)) for u in U_eff)
    aep_spacing.append(aep_sp / 1e6)   # GWh
    area_spacing.append(max(0.01, area_sp))

optimal_idx = np.argmax(np.array(aep_spacing) / np.array(area_spacing))
optimal_D   = spacings_D[optimal_idx]
print(f"[INFO] Optimal spacing (AEP/km²): {optimal_D}D")
print("[DONE] Modul 4.E — Sensitivity selesai")

# ══════════════════════════════════════════════════════════════════════════════
# 4F. Simpan wake_results.json
# ══════════════════════════════════════════════════════════════════════════════
# Posisi turbin layout terbaik dalam koordinat lat-lon
best_pos_m = np.array(results[best]["positions_m"])
deg_per_m_lon = 1 / (111000 * np.cos(np.deg2rad(center_lat)))
deg_per_m_lat = 1 / 111000
turbine_latlon = [
    [round(center_lat + p[1]*deg_per_m_lat, 5),
     round(center_lon + p[0]*deg_per_m_lon, 5)]
    for p in best_pos_m
]

wake_results = {
    "is_demo": IS_DEMO,
    "farm_center": {"lat": center_lat, "lon": center_lon},
    "rotor_diameter_m": cfg.ROTOR_DIAMETER,
    "hub_height_m": cfg.HUB_HEIGHT_REF,
    "rated_kw": cfg.P_RATED,
    "wake_model": "Jensen/Park (top-hat)",
    "weibull_k": round(k_100, 4), "weibull_lambda": round(lam_100, 4),
    "u_inf_mean": round(U_inf_mean, 3),
    "optimal_spacing_D": optimal_D,
    "layouts": {k: {
        "label": v["label"], "n_turbines": v["n_turbines"],
        "aep_gwh": v["aep_gwh"], "aep_no_wake_gwh": v["aep_no_wake_gwh"],
        "wake_loss_pct": v["wake_loss_pct"], "farm_area_km2": v["farm_area_km2"],
        "efficiency_pct": v["efficiency_pct"],
    } for k, v in results.items()},
    "turbine_positions_latlon": turbine_latlon,
    "turbine_positions_m": best_pos_m.tolist(),
    "spacing_sensitivity": {
        "spacings_D": spacings_D,
        "aep_gwh": [round(a,3) for a in aep_spacing],
        "area_km2": [round(a,3) for a in area_spacing],
        "aep_per_km2": [round(a/b,3) for a,b in zip(aep_spacing, area_spacing)],
    },
    "best_layout": best,
    "wind_direction_freq": {str(k): round(v,5) for k,v in dir_freq.items()},
}

out_wr = os.path.join(cfg.DIR_PROC, "wake_results.json")
with open(out_wr, "w") as f:
    json.dump(wake_results, f, indent=2)
files_ok.append(out_wr)
print(f"[DONE] Modul 4.F — wake_results.json tersimpan")

# ══════════════════════════════════════════════════════════════════════════════
# PLOTS
# ══════════════════════════════════════════════════════════════════════════════

# ── Plot 1: Layout comparison ─────────────────────────────────────────────────
print("[INFO] Membuat wake_layout_comparison.png...")
fig_lc, axes_lc = plt.subplots(1, 3, figsize=(18, 7), facecolor=DARK_BG)
for ax, (name, res) in zip(axes_lc, results.items()):
    ax.set_facecolor(PANEL_BG)
    pos = np.array(res["positions_m"]) / 1000  # → km
    lc = layouts[name]["color"]

    # Wake cones (arah dominan E-SE = 110°)
    dominant_dir = 110
    theta = np.deg2rad(270 - dominant_dir)
    for p in pos:
        cone_len = 10 * D / 1000  # 10D km
        ax.annotate("", xy=(p[0]+cone_len*np.cos(theta),
                             p[1]+cone_len*np.sin(theta)),
                    xytext=(p[0], p[1]),
                    arrowprops=dict(arrowstyle="-", color=ACCENT4,
                                   alpha=0.25, lw=4))

    # Turbin
    ax.scatter(pos[:,0], pos[:,1], s=120, color=lc, zorder=5,
               edgecolors="white", linewidths=0.8)

    ax.set_aspect("equal")
    ax.set_xlabel("km", color=TEXT_COL)
    ax.set_ylabel("km", color=TEXT_COL)
    ax.tick_params(colors=TEXT_COL)
    ax.set_title(f"{name}\n{res['label']}\n"
                 f"AEP={res['aep_gwh']:.1f} GWh/yr | Wake={res['wake_loss_pct']:.1f}%",
                 color=TEXT_COL, fontsize=9)
    ax.grid(True, color=GRID_COL, alpha=0.3)
    for sp in ax.spines.values(): sp.set_color(GRID_COL)

fig_lc.suptitle("Perbandingan Layout Kandidat Wind Farm — Jensen Wake Model",
                 color=TEXT_COL, fontsize=13)
plt.tight_layout()
out_lc = os.path.join(cfg.DIR_OUTPUT, "wake_layout_comparison.png")
plt.savefig(out_lc, dpi=150, bbox_inches="tight",
            facecolor=DARK_BG, edgecolor="none")
plt.close()
files_ok.append(out_lc)
print("[DONE] Modul 4.P1 — wake_layout_comparison.png tersimpan")

# ── Plot 2: Wake loss per turbine ─────────────────────────────────────────────
print("[INFO] Membuat wake_loss_per_turbine.png...")
fig_wl, axes_wl = plt.subplots(1, 3, figsize=(18, 5), facecolor=DARK_BG)
for ax, (name, res) in zip(axes_wl, results.items()):
    ax.set_facecolor(PANEL_BG)
    pos = np.array(res["positions_m"])
    N   = len(pos)
    U_eff_arr = calc_wake_field(pos, U_inf_mean, 110,
                                r0, cfg.CT, cfg.WAKE_K_ONSHORE)
    wake_loss_each = 100 * (U_inf_mean - U_eff_arr) / U_inf_mean
    colors = plt.cm.RdYlGn_r(wake_loss_each / (wake_loss_each.max()+1e-6))
    scatter = ax.scatter(pos[:,0]/1000, pos[:,1]/1000, c=wake_loss_each,
                          s=150, cmap="RdYlGn_r", vmin=0,
                          vmax=max(20, wake_loss_each.max()),
                          edgecolors="white", linewidths=0.8, zorder=5)
    plt.colorbar(scatter, ax=ax, label="Wake Loss (%)",
                  fraction=0.05, pad=0.03).ax.tick_params(colors=TEXT_COL)
    ax.set_aspect("equal")
    ax.set_title(f"{name}\nMean wake loss={wake_loss_each.mean():.1f}%",
                  color=TEXT_COL)
    ax.tick_params(colors=TEXT_COL)
    ax.set_xlabel("km", color=TEXT_COL)
    ax.set_ylabel("km", color=TEXT_COL)
    ax.grid(True, color=GRID_COL, alpha=0.3)

fig_wl.suptitle("Wake Loss Per Turbin — Arah Dominan 110° (E-SE)",
                 color=TEXT_COL, fontsize=12)
plt.tight_layout()
out_wl = os.path.join(cfg.DIR_OUTPUT, "wake_loss_per_turbine.png")
plt.savefig(out_wl, dpi=150, bbox_inches="tight",
            facecolor=DARK_BG, edgecolor="none")
plt.close()
files_ok.append(out_wl)
print("[DONE] Modul 4.P2 — wake_loss_per_turbine.png tersimpan")

# ── Plot 3: AEP vs spacing ───────────────────────────────────────────────────
print("[INFO] Membuat aep_vs_spacing.png...")
fig_sp, ax_sp = plt.subplots(figsize=(12, 6), facecolor=DARK_BG)
ax_sp.set_facecolor(PANEL_BG)

ax_sp2 = ax_sp.twinx()
aep_arr  = np.array(aep_spacing)
area_arr = np.array(area_spacing)

l1, = ax_sp.plot(spacings_D, aep_arr, "o-", color=ACCENT1, lw=2.5,
                  markersize=8, label="Total AEP (GWh/yr)")
l2, = ax_sp2.plot(spacings_D, aep_arr/area_arr, "s--", color=ACCENT2,
                   lw=2, markersize=8, label="AEP per km² (GWh/km²/yr)")

ax_sp.axvline(optimal_D, color=ACCENT4, lw=2, linestyle=":",
               label=f"Optimal spacing: {optimal_D}D")
ax_sp.axvline(7, color="#94a3b8", lw=1, linestyle="--", alpha=0.5, label="7D (layout A)")
ax_sp.axvline(10, color="#64748b", lw=1, linestyle="--", alpha=0.5, label="10D (layout B)")

ax_sp.set_xlabel("Spacing (× diameter turbin)", color=TEXT_COL, fontsize=11)
ax_sp.set_ylabel("Total AEP (GWh/yr)", color=ACCENT1, fontsize=11)
ax_sp2.set_ylabel("AEP/km² (GWh/km²/yr)", color=ACCENT2, fontsize=11)
ax_sp.set_title("Sensitivitas AEP terhadap Spacing Turbin — Layout Grid 5×5",
                 color=TEXT_COL, fontsize=12)
ax_sp.tick_params(colors=TEXT_COL, axis="both")
ax_sp2.tick_params(colors=ACCENT2, axis="y")
ax_sp.set_xticks(spacings_D)
ax_sp.set_xticklabels([f"{d}D" for d in spacings_D], color=TEXT_COL)
ax_sp.grid(True, color=GRID_COL, alpha=0.4)
ax_sp.spines["bottom"].set_color(GRID_COL)
ax_sp.spines["left"].set_color(ACCENT1)
ax_sp.spines["top"].set_visible(False)
ax_sp2.spines["right"].set_color(ACCENT2)

lines = [l1, l2, ax_sp.axvline(optimal_D, color=ACCENT4, lw=0)]
ax_sp.legend(facecolor=PANEL_BG, labelcolor=TEXT_COL, edgecolor=GRID_COL, loc="lower right")

plt.tight_layout()
out_sp = os.path.join(cfg.DIR_OUTPUT, "aep_vs_spacing.png")
plt.savefig(out_sp, dpi=150, bbox_inches="tight",
            facecolor=DARK_BG, edgecolor="none")
plt.close()
files_ok.append(out_sp)
print("[DONE] Modul 4.P3 — aep_vs_spacing.png tersimpan")

# ══════════════════════════════════════════════════════════════════════════════
elapsed = time.time() - t0
print("\n" + "=" * 60)
print(f"  [DONE] Modul 4 — Wake Analysis selesai dalam {elapsed:.1f}s")
print(f"  File berhasil : {len(files_ok)}")
for f in files_ok:
    print(f"    [OK] {os.path.basename(f)}")
print(f"\n  Ringkasan AEP:")
for name, res in results.items():
    print(f"    {name}: {res['aep_gwh']:.2f} GWh/yr | Wake={res['wake_loss_pct']:.1f}%")
print("=" * 60)
