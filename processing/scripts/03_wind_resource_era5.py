"""
03_wind_resource_era5.py — Analisis Wind Resource dari ERA5 1980-2025

Input  : Data/data_zahy/ERA5_Tulungagung_1hr_0125_u10_YYYY.nc
         Data/data_zahy/ERA5_Tulungagung_1hr_0125_v10_YYYY.nc
Output : processing/output/windrose_tulungagung.png
         processing/output/wind_power_density.png
         processing/output/weibull_params.npz
         processing/output/era5_wind_stats.txt

Run: python processing/scripts/03_wind_resource_era5.py
"""

import os
import sys
import glob
import numpy as np

try:
    import xarray as xr
    HAS_XR = True
except ImportError:
    HAS_XR = False
    print("[ERROR] pip install xarray netCDF4"); sys.exit(1)

try:
    import matplotlib.pyplot as plt
    import matplotlib.colors as mcolors
    from matplotlib.patches import FancyArrowPatch
    import matplotlib.gridspec as gridspec
    HAS_MPL = True
except ImportError:
    HAS_MPL = False

try:
    from scipy import stats
    from scipy.special import gamma
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False
    print("[WARN] scipy tidak ada — pip install scipy")

try:
    from windrose import WindroseAxes
    HAS_WINDROSE = True
except ImportError:
    HAS_WINDROSE = False
    print("[WARN] windrose tidak ada — pip install windrose")

# ── Paths ───────────────────────────────────────────────────────────────────
BASE_DIR  = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR  = os.path.normpath(os.path.join(BASE_DIR, '..', '..', 'Data', 'data_zahy'))
OUT_DIR   = os.path.join(BASE_DIR, 'processing', 'output')
FILE_HEAD = 'ERA5_Tulungagung_1hr_0125_'
os.makedirs(OUT_DIR, exist_ok=True)

# Domain & point referensi
DOMAIN   = {'lat_min': -9.29, 'lat_max': -7.29, 'lon_min': 110.8, 'lon_max': 112.8}
NIYAMA   = {'lat': -8.292, 'lon': 111.797, 'name': 'Niyama Beach'}
CENTER   = {'lat': -8.065, 'lon': 111.905, 'name': 'Tulungagung'}
AIR_DENSITY = 1.225  # kg/m³ at sea level (tropical approx)


def preprocess(ds):
    for coord in ['expver', 'number']:
        if coord in ds.coords:
            ds = ds.drop_vars(coord, errors='ignore')
    if 'valid_time' in ds.dims:
        ds = ds.rename({'valid_time': 'time'})
    elif 'valid_time' in ds.coords and 'valid_time' not in ds.dims:
        ds = ds.rename({'valid_time': 'time'})
    return ds


def load_wind_full(data_dir, file_head, years=range(1980, 2026), chunks={'time': 8760}):
    """Load u10, v10 untuk seluruh periode"""
    print(f"[INFO] Loading u10, v10 ({years.start}–{years.stop-1})...")
    u_files = sorted([f for f in glob.glob(os.path.join(data_dir, f'{file_head}u10_*.nc'))
                      if not os.path.basename(f).startswith('._')
                      and any(f.endswith(f'_{y}.nc') for y in years)])
    v_files = sorted([f for f in glob.glob(os.path.join(data_dir, f'{file_head}v10_*.nc'))
                      if not os.path.basename(f).startswith('._')
                      and any(f.endswith(f'_{y}.nc') for y in years)])

    if not u_files or not v_files:
        raise FileNotFoundError(f"Tidak ada file u10/v10 di {data_dir}")

    print(f"       {len(u_files)} file u10, {len(v_files)} file v10")
    ds_u = xr.open_mfdataset(u_files, combine='by_coords',
                              chunks=chunks, preprocess=preprocess)
    ds_v = xr.open_mfdataset(v_files, combine='by_coords',
                              chunks=chunks, preprocess=preprocess)
    # Rename lat/lon jika perlu
    rename_map = {}
    for name in ['latitude', 'lat']:
        if name in ds_u.coords and name != 'latitude':
            rename_map[name] = 'latitude'
    for name in ['longitude', 'lon']:
        if name in ds_u.coords and name != 'longitude':
            rename_map[name] = 'longitude'
    if rename_map:
        ds_u = ds_u.rename(rename_map)
        ds_v = ds_v.rename(rename_map)

    ds = xr.merge([ds_u, ds_v])
    # Pastikan variabel bernama u10, v10
    varnames = list(ds.data_vars)
    if 'u10' not in ds and len(varnames) >= 2:
        ds = ds.rename({varnames[0]: 'u10', varnames[1]: 'v10'})
    elif 'u10' not in ds and len(varnames) == 1:
        # Coba dari masing-masing
        u_var = list(ds_u.data_vars)[0]
        v_var = list(ds_v.data_vars)[0]
        ds['u10'] = ds_u[u_var]
        ds['v10'] = ds_v[v_var]

    ds['wspd'] = np.sqrt(ds['u10']**2 + ds['v10']**2)
    ds['wdir'] = (270 - np.degrees(np.arctan2(ds['v10'], ds['u10']))) % 360
    ds['wpd']  = 0.5 * AIR_DENSITY * ds['wspd']**3  # W/m²
    print(f"[INFO] Domain: lat {float(ds.latitude.min()):.2f}–{float(ds.latitude.max()):.2f}  "
          f"lon {float(ds.longitude.min()):.2f}–{float(ds.longitude.max()):.2f}")
    return ds


def fit_weibull_grid(wspd_data):
    """
    Fit distribusi Weibull (shape k, scale A) untuk setiap grid point.
    wspd_data: np.array (lat, lon, time) atau (time,) untuk satu titik
    """
    if not HAS_SCIPY:
        return None, None

    shape_in = wspd_data.shape
    if len(shape_in) == 1:
        ws = wspd_data[np.isfinite(wspd_data) & (wspd_data > 0)]
        if len(ws) < 100:
            return np.nan, np.nan
        k, _, A = stats.weibull_min.fit(ws, floc=0)
        return k, A

    # Grid mode
    nlat, nlon, nt = shape_in
    k_arr = np.full((nlat, nlon), np.nan)
    A_arr = np.full((nlat, nlon), np.nan)
    for i in range(nlat):
        for j in range(nlon):
            ws = wspd_data[i, j, :]
            ws = ws[np.isfinite(ws) & (ws > 0)]
            if len(ws) < 100:
                continue
            try:
                k, _, A = stats.weibull_min.fit(ws, floc=0)
                k_arr[i, j] = k
                A_arr[i, j] = A
            except Exception:
                pass
    return k_arr, A_arr


def plot_windrose(wspd_niyama, wdir_niyama, out_path):
    """Plot wind rose di titik Niyama Beach"""
    print("[INFO] Membuat wind rose...")

    ws = np.array(wspd_niyama)
    wd = np.array(wdir_niyama)
    mask = np.isfinite(ws) & np.isfinite(wd)
    ws, wd = ws[mask], wd[mask]

    if HAS_WINDROSE:
        fig = plt.figure(figsize=(10, 10), facecolor='#0a0e1a')
        ax  = WindroseAxes.from_ax(fig=fig)
        ax.set_facecolor('#0d1117')
        cmap = plt.cm.plasma
        ax.bar(wd, ws, normed=True, opening=0.9, edgecolor='white',
               linewidth=0.3, nsector=16, cmap=cmap, bins=6)
        ax.set_legend(title='Kec. Angin (m/s)', loc='lower right',
                      facecolor='#1a1e2e', edgecolor='#444',
                      labelcolor='white', fontsize=9)
        ax.set_title(f'Wind Rose — {NIYAMA["name"]}, Tulungagung\n'
                     f'ERA5 1980–2025 | N={len(ws):,} data (hourly)',
                     color='white', fontsize=13, pad=15)
        for txt in ax.texts:
            txt.set_color('white')
        for lbl in ax.get_xticklabels() + ax.get_yticklabels():
            lbl.set_color('white')
    else:
        # Fallback: histogram arah angin
        fig, axes = plt.subplots(1, 2, figsize=(14, 6), facecolor='#0a0e1a')
        fig.suptitle(f'Wind Statistics — {NIYAMA["name"]} (ERA5 1980–2025)',
                     color='white', fontsize=13)

        ax = axes[0]
        ax.set_facecolor('#0d1117')
        bins_dir = np.arange(0, 361, 22.5)
        hist, _ = np.histogram(wd, bins=bins_dir)
        bar_centers = bins_dir[:-1] + 11.25
        ax.bar(bar_centers, hist/hist.sum()*100, width=20,
               color='#00bfff', edgecolor='#0a0e1a', alpha=0.85)
        ax.set_xlabel('Arah Angin (°)', color='white')
        ax.set_ylabel('Frekuensi (%)', color='white')
        ax.set_title('Distribusi Arah Angin', color='white')
        ax.tick_params(colors='white')
        ax.set_facecolor('#0d1117')

        ax = axes[1]
        ax.set_facecolor('#0d1117')
        ax.hist(ws, bins=50, color='#ff6b6b', edgecolor='#0a0e1a',
                alpha=0.85, density=True)
        if HAS_SCIPY:
            x = np.linspace(0, ws.max(), 200)
            k, _, A = stats.weibull_min.fit(ws, floc=0)
            pdf = stats.weibull_min.pdf(x, k, loc=0, scale=A)
            ax.plot(x, pdf, 'y-', lw=2.5, label=f'Weibull k={k:.2f}, A={A:.2f} m/s')
            ax.legend(facecolor='#1a1e2e', labelcolor='white', edgecolor='#555')
        ax.set_xlabel('Kecepatan Angin (m/s)', color='white')
        ax.set_ylabel('Probabilitas Densitas', color='white')
        ax.set_title('Distribusi Kecepatan Angin', color='white')
        ax.tick_params(colors='white')
        for a in axes:
            a.spines[['bottom','left','top','right']].set_edgecolor('#444')
            a.grid(True, color='#222', linewidth=0.5, linestyle='--', alpha=0.5)

    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches='tight', facecolor='#0a0e1a')
    plt.close()
    print(f"[DONE] Wind rose: {out_path}")


def plot_wind_power_density(ds_mean, out_path, lsm_path=None):
    """Peta Wind Power Density rata-rata 1980–2025"""
    print("[INFO] Membuat peta Wind Power Density...")

    wpd_mean = ds_mean['wpd']   # W/m²

    # Load land-sea mask jika ada
    lsm = None
    if lsm_path and os.path.exists(lsm_path):
        try:
            lsm_ds = xr.open_dataset(lsm_path)
            lsm = lsm_ds['lsm'].values if 'lsm' in lsm_ds else None
        except Exception:
            pass

    lats = wpd_mean.latitude.values
    lons = wpd_mean.longitude.values
    wpd  = wpd_mean.values

    fig, axes = plt.subplots(1, 2, figsize=(18, 8), facecolor='#0a0e1a')
    fig.suptitle('Wind Power Density — Tulungagung Region (ERA5 1980–2025)',
                 color='white', fontsize=15, y=1.01)

    cmap_wpd = plt.cm.inferno
    norm_wpd = mcolors.Normalize(vmin=0, vmax=np.nanpercentile(wpd, 97))

    for ax, title_extra in zip(axes, ['All Grid Points', 'Ocean Only (masked)']):
        ax.set_facecolor('#0d1117')
        wpd_plot = wpd.copy()
        if 'Ocean' in title_extra and lsm is not None:
            # crop lsm ke domain yang sama
            try:
                lsm_crop = xr.open_dataset(lsm_path)['lsm'].sel(
                    latitude=slice(lats.max(), lats.min()),
                    longitude=slice(lons.min(), lons.max())
                ).values
                if lsm_crop.shape == wpd_plot.shape:
                    wpd_plot = np.where(lsm_crop < 0.5, wpd_plot, np.nan)
            except Exception:
                pass

        cf = ax.contourf(lons, lats, wpd_plot, levels=20,
                         cmap=cmap_wpd, norm=norm_wpd)
        cbar = plt.colorbar(cf, ax=ax, shrink=0.8)
        cbar.set_label('WPD (W/m²)', color='white')
        cbar.ax.yaxis.set_tick_params(color='white')
        plt.setp(cbar.ax.yaxis.get_ticklabels(), color='white')

        ax.plot(NIYAMA['lon'], NIYAMA['lat'],  'w*', ms=14, zorder=5,
                label='Niyama Beach')
        ax.plot(CENTER['lon'], CENTER['lat'],  'wo', ms=10, zorder=5,
                label='Tulungagung')

        ax.set_title(f'WPD Mean — {title_extra}', color='white', fontsize=12)
        ax.set_xlabel('Longitude (°E)', color='white')
        ax.set_ylabel('Latitude (°S)', color='white')
        ax.tick_params(colors='white')
        ax.spines[['bottom','left','top','right']].set_edgecolor('#444')
        ax.legend(facecolor='#1a1e2e', edgecolor='#555', labelcolor='white', fontsize=9)
        ax.grid(True, color='#333', linewidth=0.4, linestyle='--', alpha=0.5)

    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches='tight', facecolor='#0a0e1a')
    plt.close()
    print(f"[DONE] WPD map: {out_path}")


def find_top5_wpd(ds_mean):
    """Identifikasi 5 lokasi WPD tertinggi di domain"""
    wpd = ds_mean['wpd'].values
    lats = ds_mean.latitude.values
    lons = ds_mean.longitude.values

    flat_idx = np.argsort(wpd.ravel())[::-1][:5]
    lat_idx, lon_idx = np.unravel_index(flat_idx, wpd.shape)

    print("\n── TOP 5 LOKASI WIND POWER DENSITY ────────────────────────────")
    print(f"  {'Rank':<5} {'Lat':>8} {'Lon':>9} {'WPD (W/m²)':>12}")
    print("  " + "-"*40)
    for rank, (li, loi) in enumerate(zip(lat_idx, lon_idx), 1):
        print(f"  #{rank:<4} {lats[li]:>8.3f} {lons[loi]:>9.3f} {wpd[li,loi]:>12.1f}")


def save_stats(wspd_niyama, wdir_niyama, k, A, out_path):
    """Simpan statistik angin ke file teks"""
    ws = np.array(wspd_niyama)
    ws = ws[np.isfinite(ws) & (ws > 0)]
    wpd_mean_niyama = 0.5 * AIR_DENSITY * np.mean(ws**3)

    lines = [
        "=" * 60,
        " WIND RESOURCE STATISTICS — NIYAMA BEACH, TULUNGAGUNG",
        " ERA5 1980-2025 (46 tahun, hourly)",
        "=" * 60,
        f"  Lokasi          : Niyama Beach ({NIYAMA['lat']}°S, {NIYAMA['lon']}°E)",
        f"  Periode         : 1980–2025",
        f"  N data          : {len(ws):,} timestep",
        "",
        "  STATISTIK KECEPATAN ANGIN (m/s):",
        f"  Mean            : {np.mean(ws):.3f}",
        f"  Median          : {np.median(ws):.3f}",
        f"  Std             : {np.std(ws):.3f}",
        f"  Min / Max       : {ws.min():.3f} / {ws.max():.3f}",
        f"  P75             : {np.percentile(ws, 75):.3f}",
        f"  P90             : {np.percentile(ws, 90):.3f}",
        f"  P99             : {np.percentile(ws, 99):.3f}",
        "",
        "  DISTRIBUSI WEIBULL:",
        f"  Shape (k)       : {k:.4f}" if np.isfinite(k) else "  Shape (k)       : N/A",
        f"  Scale (A)       : {A:.4f} m/s" if np.isfinite(A) else "  Scale (A)       : N/A",
        "",
        "  WIND POWER DENSITY (@ 10m AGL):",
        f"  WPD mean        : {wpd_mean_niyama:.1f} W/m²",
        f"  Kelas IEC       : {_wpd_class(wpd_mean_niyama)}",
        "=" * 60,
    ]
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    for line in lines:
        print(line)


def _wpd_class(wpd):
    """Kelas potensi angin berdasarkan WPD"""
    if wpd < 100:   return "Kelas 1 (Sangat Rendah, < 100 W/m²)"
    if wpd < 200:   return "Kelas 2 (Rendah, 100–200 W/m²)"
    if wpd < 300:   return "Kelas 3 (Sedang, 200–300 W/m²)"
    if wpd < 400:   return "Kelas 4 (Baik, 300–400 W/m²)"
    if wpd < 500:   return "Kelas 5 (Sangat Baik, 400–500 W/m²)"
    return "Kelas 6+ (Luar Biasa, > 500 W/m²)"


# ── MAIN ────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    print("=" * 65)
    print("  TAHAP 3 — Wind Resource Assessment dari ERA5")
    print("=" * 65)

    # Load data
    ds = load_wind_full(DATA_DIR, FILE_HEAD)

    # Seleksi titik Niyama
    print("[INFO] Mengekstrak data di Niyama Beach...")
    ds_niyama = ds.sel(latitude=NIYAMA['lat'], longitude=NIYAMA['lon'],
                       method='nearest').compute()
    wspd_niyama = ds_niyama['wspd'].values
    wdir_niyama = ds_niyama['wdir'].values

    # Mean temporal untuk peta
    print("[INFO] Menghitung rata-rata temporal (ini mungkin makan waktu)...")
    ds_mean = ds.mean(dim='time').compute()

    # Wind rose
    rose_path = os.path.join(OUT_DIR, 'windrose_tulungagung.png')
    plot_windrose(wspd_niyama, wdir_niyama, rose_path)

    # WPD map
    wpd_path = os.path.join(OUT_DIR, 'wind_power_density.png')
    lsm_path = os.path.join(DATA_DIR, 'ERA5_Tulungagung_1hr_0125_landseamask.nc')
    plot_wind_power_density(ds_mean, wpd_path, lsm_path)

    # Top 5 lokasi
    find_top5_wpd(ds_mean)

    # Weibull fit di Niyama
    print("\n[INFO] Fitting distribusi Weibull di Niyama Beach...")
    k, A = fit_weibull_grid(wspd_niyama)
    np.savez(os.path.join(OUT_DIR, 'weibull_params_niyama.npz'), k=k, A=A)

    # Simpan statistik
    stats_path = os.path.join(OUT_DIR, 'era5_wind_stats.txt')
    save_stats(wspd_niyama, wdir_niyama, k, A, stats_path)

    print(f"\n[DONE] Tahap 3 — Wind Resource ERA5 selesai")
    print(f"       Wind Rose : {rose_path}")
    print(f"       WPD Map   : {wpd_path}")
    print(f"       Stats     : {stats_path}")
