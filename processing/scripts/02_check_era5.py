"""
02_check_era5.py — Validasi semua data ERA5 yang tersedia

Membaca data dari Data/data_zahy/ dan melaporkan:
- Variabel yang ada
- Periode temporal
- Resolusi spasial
- Variabel yang KURANG untuk WRF

Run: python processing/scripts/02_check_era5.py
"""

import os
import glob
import sys
import numpy as np

try:
    import xarray as xr
    HAS_XR = True
except ImportError:
    HAS_XR = False
    print("[WARN] xarray tidak terinstall — install: pip install xarray netCDF4")

try:
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    HAS_MPL = True
except ImportError:
    HAS_MPL = False

# ── Paths ───────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BASE_DIR, '..', '..', 'Data', 'data_zahy')
DATA_DIR = os.path.normpath(DATA_DIR)
OUT_DIR  = os.path.join(BASE_DIR, 'processing', 'output')
FILE_HEAD = 'ERA5_Tulungagung_1hr_0125_'
os.makedirs(OUT_DIR, exist_ok=True)

# Titik Niyama Beach
NIYAMA_LAT = -8.292
NIYAMA_LON = 111.797

# ── Variabel yang dibutuhkan ─────────────────────────────────────────────────
VARS_EXISTING = {
    'u10':    'u10 — 10m U-wind  (CDS: 10m_u_component_of_wind)',
    'v10':    'v10 — 10m V-wind  (CDS: 10m_v_component_of_wind)',
    'temp2m': 't2m — 2m Temp     (CDS: 2m_temperature)',
    'ssrd':   'ssrd — Solar Rad  (CDS: surface_solar_radiation_downwards)',
    'swh':    'swh — Wave Height (ERA5-Ocean)',
    'mwp':    'mwp — Wave Period (ERA5-Ocean)',
    'mwd':    'mwd — Wave Dir    (ERA5-Ocean)',
    'precip': 'precip — Precipitation',
}

# Variabel KURANG untuk WRF (single levels)
VARS_MISSING_SINGLE = {
    'sp':    'surface_pressure             ← WAJIB untuk WRF (batas bawah atmosfer)',
    'msl':   'mean_sea_level_pressure      ← WAJIB referensi tekanan',
    'sst':   'sea_surface_temperature      ← WAJIB kondisi laut Selatan Jawa',
    'stl1':  'soil_temperature_level_1     ← Noah LSM WRF',
    'stl2':  'soil_temperature_level_2     ← Noah LSM WRF',
    'stl3':  'soil_temperature_level_3     ← Noah LSM WRF',
    'stl4':  'soil_temperature_level_4     ← Noah LSM WRF',
    'swvl1': 'volumetric_soil_water_layer_1 ← Noah LSM WRF',
    'swvl2': 'volumetric_soil_water_layer_2 ← Noah LSM WRF',
    'swvl3': 'volumetric_soil_water_layer_3 ← Noah LSM WRF',
    'swvl4': 'volumetric_soil_water_layer_4 ← Noah LSM WRF',
    'sd':    'snow_depth                   ← Dibutuhkan WPS',
}

# Variabel KURANG untuk WRF (pressure levels)
VARS_MISSING_PRESSURE = {
    'u':     'u_component_of_wind       (pressure levels)',
    'v':     'v_component_of_wind       (pressure levels)',
    't':     'temperature               (pressure levels)',
    'q':     'specific_humidity         (pressure levels)',
    'z':     'geopotential              (pressure levels)',
}


def scan_available(data_dir, file_head, var_dict):
    """Scan file per-tahun dan laporkan ketersediaan"""
    results = {}
    for var in var_dict:
        # Cek subfolder precip juga
        patterns = [
            os.path.join(data_dir, f'{file_head}{var}_*.nc'),
            os.path.join(data_dir, 'precip', f'{file_head}{var}_*.nc'),
        ]
        files = []
        for pat in patterns:
            files.extend(glob.glob(pat))
        files = sorted([f for f in files if not os.path.basename(f).startswith('._')])
        years = []
        for f in files:
            bn = os.path.basename(f).replace(f'{file_head}{var}_', '').replace('.nc','')
            if bn.isdigit() and 1979 < int(bn) < 2030:
                years.append(int(bn))
        results[var] = sorted(set(years))
    return results


def check_gaps(years, expected_start=1980, expected_end=2025):
    """Cek gap tahun"""
    expected = set(range(expected_start, expected_end + 1))
    available = set(years)
    missing = sorted(expected - available)
    return missing


def inspect_one_file(data_dir, file_head, var, year=2000):
    """Baca 1 file untuk cek variabel internal dan resolusi"""
    for d in [data_dir, os.path.join(data_dir, 'precip')]:
        path = os.path.join(d, f'{file_head}{var}_{year}.nc')
        if os.path.exists(path):
            try:
                ds = xr.open_dataset(path)
                return ds
            except Exception:
                pass
    return None


def plot_wind_timeseries(data_dir, file_head, out_path):
    """Plot time series u10+v10 di grid terdekat Niyama (2000–2005 sample)"""
    if not HAS_MPL:
        return
    print("\n[INFO] Plot time series angin (sample 2000–2005)...")

    years_sample = range(2000, 2006)
    u_list, v_list = [], []

    def preprocess(ds):
        for dim in ['valid_time', 'expver', 'number']:
            if dim in ds.dims:
                ds = ds.rename({'valid_time': 'time'}) if dim == 'valid_time' else ds
            if dim in ds.coords and dim not in ds.dims:
                ds = ds.drop_vars(dim, errors='ignore')
        return ds

    for yr in years_sample:
        for var, lst in [('u10', u_list), ('v10', v_list)]:
            path = os.path.join(data_dir, f'{file_head}{var}_{yr}.nc')
            if os.path.exists(path):
                ds = xr.open_dataset(path).pipe(preprocess)
                time_dim = 'time' if 'time' in ds.dims else 'valid_time'
                lat_dim  = 'latitude'  if 'latitude'  in ds.dims else 'lat'
                lon_dim  = 'longitude' if 'longitude' in ds.dims else 'lon'
                varname = [v for v in ds.data_vars][0]
                sel = ds[varname].sel(
                    {lat_dim: NIYAMA_LAT, lon_dim: NIYAMA_LON},
                    method='nearest'
                )
                lst.append(sel)
                ds.close()

    if not u_list or not v_list:
        print("[WARN] Tidak ada data u10/v10 untuk plot.")
        return

    u_ts = xr.concat(u_list, dim='time')
    v_ts = xr.concat(v_list, dim='time')
    wspd = np.sqrt(u_ts**2 + v_ts**2)

    # Daily mean untuk plot bersih
    wspd_daily = wspd.resample(time='1D').mean()

    fig, axes = plt.subplots(3, 1, figsize=(15, 10), facecolor='#0a0e1a',
                             sharex=True)
    fig.suptitle('ERA5 10m Wind Speed — Niyama Beach, Tulungagung (2000–2005)',
                 color='white', fontsize=14, y=0.98)

    colors = ['#00bfff', '#ff6b6b', '#ffd700']
    labels = ['U10 (m/s)', 'V10 (m/s)', 'Wind Speed (m/s)']
    data_list = [u_ts.resample(time='1D').mean(),
                 v_ts.resample(time='1D').mean(),
                 wspd_daily]

    for ax, dat, col, lbl in zip(axes, data_list, colors, labels):
        ax.set_facecolor('#0d1117')
        ax.plot(dat.time.values, dat.values, color=col, linewidth=0.7, alpha=0.9)
        ax.fill_between(dat.time.values, dat.values, alpha=0.2, color=col)
        ax.set_ylabel(lbl, color='white', fontsize=11)
        ax.tick_params(colors='white', labelsize=9)
        ax.spines[['bottom','left','top','right']].set_edgecolor('#444')
        ax.grid(True, color='#222', linewidth=0.5, linestyle='--', alpha=0.6)
        ax.axhline(0, color='#555', linewidth=0.5)

    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    axes[-1].xaxis.set_major_locator(mdates.MonthLocator(interval=6))
    plt.setp(axes[-1].xaxis.get_ticklabels(), rotation=30, ha='right', color='white')

    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches='tight', facecolor='#0a0e1a')
    plt.close()
    print(f"[DONE] Timeseries plot: {out_path}")


# ── MAIN ────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    print("=" * 65)
    print("  TAHAP 2 — Validasi Data ERA5")
    print("=" * 65)
    print(f"  Data dir: {DATA_DIR}\n")

    if not os.path.isdir(DATA_DIR):
        print(f"[ERROR] Folder tidak ditemukan: {DATA_DIR}")
        sys.exit(1)

    # ── 1. Scan variabel yang ada ────────────────────────────────────────
    print("── VARIABEL YANG TERSEDIA ──────────────────────────────────────")
    available = scan_available(DATA_DIR, FILE_HEAD, VARS_EXISTING)
    all_ok = True
    for var, years in available.items():
        if years:
            gaps = check_gaps(years)
            gap_str = f"  ⚠ GAP: {gaps}" if gaps else ""
            print(f"  ✅ {VARS_EXISTING[var]}")
            print(f"      Tahun: {min(years)}–{max(years)} ({len(years)} file){gap_str}")
        else:
            all_ok = False
            print(f"  ❌ {VARS_EXISTING.get(var, var)} — TIDAK DITEMUKAN")

    # ── 2. Inspeksi 1 file untuk cek variabel internal ──────────────────
    print("\n── CEK VARIABEL INTERNAL (sample tahun 2000) ───────────────────")
    for var in ['u10', 'v10', 'temp2m']:
        ds = inspect_one_file(DATA_DIR, FILE_HEAD, var)
        if ds is not None and HAS_XR:
            time_dim = 'time' if 'time' in ds.dims else 'valid_time'
            lat_dim  = 'latitude' if 'latitude' in ds.dims else 'lat'
            lon_dim  = 'longitude' if 'longitude' in ds.dims else 'lon'
            n_time   = ds.dims.get(time_dim, '?')
            lats     = ds.coords.get(lat_dim, None)
            lons     = ds.coords.get(lon_dim, None)
            res      = abs(float(lats[1] - lats[0])) if lats is not None and len(lats) > 1 else '?'
            dvars    = list(ds.data_vars)
            print(f"  {var}: dims={dict(ds.dims)}  vars={dvars}  res={res:.4f}°")
            ds.close()

    # ── 3. Laporan variabel yang KURANG ──────────────────────────────────
    print("\n── VARIABEL YANG KURANG (untuk WRF) ────────────────────────────")
    print("\n  Single Level (harus didownload dari CDS):")
    for var, desc in VARS_MISSING_SINGLE.items():
        # Cek apakah ada di folder
        paths = glob.glob(os.path.join(DATA_DIR, f'*{var}*.nc'))
        if paths:
            print(f"  ✅ {var} — sudah ada ({len(paths)} file)")
        else:
            print(f"  ❌ {var} — {desc}")

    print("\n  Pressure Levels (harus didownload dari CDS — ERA5 Pressure Levels):")
    for var, desc in VARS_MISSING_PRESSURE.items():
        print(f"  ❌ {var} — {desc}")

    # ── 4. Instruksi download CDS ─────────────────────────────────────────
    print("\n── INSTRUKSI DOWNLOAD CDS API ──────────────────────────────────")
    print("""
  Untuk download ERA5 missing variables, gunakan skrip Python berikut
  (pastikan sudah install cdsapi: pip install cdsapi):

  import cdsapi
  c = cdsapi.Client()

  # Single Levels yang kurang:
  c.retrieve('reanalysis-era5-single-levels', {
      'product_type': 'reanalysis',
      'variable': [
          'surface_pressure', 'mean_sea_level_pressure',
          'sea_surface_temperature',
          'soil_temperature_level_1', 'soil_temperature_level_2',
          'soil_temperature_level_3', 'soil_temperature_level_4',
          'volumetric_soil_water_layer_1', 'volumetric_soil_water_layer_2',
          'volumetric_soil_water_layer_3', 'volumetric_soil_water_layer_4',
          'snow_depth',
      ],
      'year': '2022',      # ganti sesuai kebutuhan
      'month': ['07', '08'],  # Juli-Agustus (kemarau)
      'day': [f'{d:02d}' for d in range(1, 32)],
      'time': [f'{h:02d}:00' for h in range(24)],
      'area': [-5.0, 108.0, -11.0, 116.0],  # N, W, S, E
      'format': 'netcdf',
      'grid': [0.25, 0.25],
  }, 'era5_single_levels_wrf_2022_JulAug.nc')

  # Pressure Levels:
  c.retrieve('reanalysis-era5-pressure-levels', {
      'product_type': 'reanalysis',
      'variable': ['u_component_of_wind', 'v_component_of_wind',
                   'temperature', 'specific_humidity', 'geopotential'],
      'pressure_level': ['1000', '925', '850', '700', '600',
                         '500', '400', '300', '250', '200',
                         '150', '100', '50'],  # 13 level (efisien)
      'year': '2022',
      'month': ['07', '08'],
      'day': [f'{d:02d}' for d in range(1, 32)],
      'time': [f'{h:02d}:00' for h in range(24)],
      'area': [-5.0, 108.0, -11.0, 116.0],
      'format': 'netcdf',
      'grid': [0.25, 0.25],
  }, 'era5_pressure_levels_wrf_2022_JulAug.nc')
""")

    # ── 5. Plot timeseries ────────────────────────────────────────────────
    if HAS_XR and HAS_MPL:
        ts_path = os.path.join(OUT_DIR, 'era5_timeseries_wind.png')
        plot_wind_timeseries(DATA_DIR, FILE_HEAD, ts_path)

    print(f"\n[DONE] Tahap 2 — Validasi ERA5 selesai")
