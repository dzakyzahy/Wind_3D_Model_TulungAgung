"""
04_era5_dem_to_json.py — Konversi ERA5 + DEM → wind_data.json untuk Three.js

Input  : Data/data_zahy/ERA5_..._u10_*.nc, v10_*.nc
         Data/Demnas/demnas_tulungagung_mosaic.tif  (atau fallback ke sintetis)
Output : visualization/wind_data.json

Mode:
  - 'real'  : pakai data ERA5 + DEM nyata (default)
  - 'demo'  : pakai data sintetis jika DEM/ERA5 belum siap

Run: python processing/scripts/04_era5_dem_to_json.py
"""

import os
import sys
if hasattr(sys, 'stdout') and hasattr(sys.stdout, 'reconfigure'):
    try: sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass
if hasattr(sys, 'stderr') and hasattr(sys.stderr, 'reconfigure'):
    try: sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass
import json
import glob
import numpy as np

try:
    import xarray as xr
    HAS_XR = True
except ImportError:
    HAS_XR = False
    print("[ERROR] pip install xarray netCDF4"); sys.exit(1)

try:
    import rasterio
    from rasterio.warp import reproject, Resampling, calculate_default_transform
    from rasterio.crs import CRS
    HAS_RASTERIO = True
except ImportError:
    HAS_RASTERIO = False
    print("[WARN] rasterio tidak ada — akan pakai mode demo DEM")

try:
    from scipy.ndimage import zoom, gaussian_filter, map_coordinates
    from scipy.interpolate import RegularGridInterpolator
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

# ── Paths ───────────────────────────────────────────────────────────────────
BASE_DIR  = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR  = os.path.normpath(os.path.join(BASE_DIR, '..', '..', 'Data', 'data_zahy'))
DEM_PATH  = os.path.join(BASE_DIR, 'Data', 'Demnas', 'processed', 'dem_270m.tif')
OUT_JSON  = os.path.join(BASE_DIR, 'visualization', 'wind_data.json')
OUT_JSON_PROC = os.path.join(BASE_DIR, 'Data', 'processed', 'wind_data.json')
FILE_HEAD = 'ERA5_Tulungagung_1hr_0125_'

# ── Bounding box domain (dari E_helpers.py) ─────────────────────────────────
DOMAIN = {'lat_min': -9.29, 'lat_max': -7.29, 'lon_min': 110.8, 'lon_max': 112.8}
NIYAMA = {'lat': -8.292, 'lon': 111.797}

# Output grid untuk visualisasi
GRID_SIZE = 100    # 100x100 grid points untuk browser
LEVELS_M  = [50, 100, 200]  # ketinggian AGL untuk analisis
AIR_RHO   = 1.225


def preprocess(ds):
    for coord in ['expver', 'number']:
        if coord in ds.coords:
            ds = ds.drop_vars(coord, errors='ignore')
    if 'valid_time' in ds.dims:
        ds = ds.rename({'valid_time': 'time'})
    return ds


def load_era5_mean_wind(data_dir, file_head, years=range(1980, 2026)):
    """Load rata-rata angin temporal dari u10, v10"""
    print("[INFO] Loading ERA5 u10/v10 (mean temporal)...")
    u_files = sorted([f for f in glob.glob(os.path.join(data_dir, f'{file_head}u10_*.nc'))
                      if not os.path.basename(f).startswith('._')
                      and any(f.endswith(f'_{y}.nc') for y in years)])[:10]  # 10 tahun pertama sbg sample
    v_files = sorted([f for f in glob.glob(os.path.join(data_dir, f'{file_head}v10_*.nc'))
                      if not os.path.basename(f).startswith('._')
                      and any(f.endswith(f'_{y}.nc') for y in years)])[:10]

    if not u_files:
        raise FileNotFoundError(f"Tidak ada u10 files di {data_dir}")

    print(f"       Menggunakan {len(u_files)} tahun sebagai representative sample...")
    ds_u = xr.open_mfdataset(u_files, combine='by_coords',
                              chunks={'time': 8760}, preprocess=preprocess)
    ds_v = xr.open_mfdataset(v_files, combine='by_coords',
                              chunks={'time': 8760}, preprocess=preprocess)

    # Crop ke domain
    lat_dim = 'latitude' if 'latitude' in ds_u.dims else 'lat'
    lon_dim = 'longitude' if 'longitude' in ds_u.dims else 'lon'

    ds_u = ds_u.sel({
        lat_dim: slice(DOMAIN['lat_max'], DOMAIN['lat_min']),
        lon_dim: slice(DOMAIN['lon_min'], DOMAIN['lon_max']),
    })
    ds_v = ds_v.sel({
        lat_dim: slice(DOMAIN['lat_max'], DOMAIN['lat_min']),
        lon_dim: slice(DOMAIN['lon_min'], DOMAIN['lon_max']),
    })

    uv = list(ds_u.data_vars)[0]
    vv = list(ds_v.data_vars)[0]
    u_mean = ds_u[uv].mean(dim='time').compute()
    v_mean = ds_v[vv].mean(dim='time').compute()

    # Juga hitung percentile 75, 90
    u_p75  = ds_u[uv].quantile(0.75, dim='time').compute()
    u_p90  = ds_u[uv].quantile(0.90, dim='time').compute()
    v_p75  = ds_v[vv].quantile(0.75, dim='time').compute()
    v_p90  = ds_v[vv].quantile(0.90, dim='time').compute()

    lats = u_mean[lat_dim].values
    lons = u_mean[lon_dim].values

    return {
        'lats': lats, 'lons': lons,
        'u_mean': u_mean.values, 'v_mean': v_mean.values,
        'u_p75': u_p75.values,   'v_p75': v_p75.values,
        'u_p90': u_p90.values,   'v_p90': v_p90.values,
    }


def load_dem_resampled(dem_path, grid_size=100):
    """Load DEMNAS daratan dan BATNAS batimetri laut, resample & merge ke grid_size x grid_size"""
    batnas_path = os.path.join(BASE_DIR, 'Data', 'Batnas', 'BATNAS_110E-115E_10S-05S_MSL_v1.6.tif')
    
    # 1. Load DEMNAS (Daratan)
    if os.path.exists(dem_path) and HAS_SCIPY:
        import tifffile
        print(f"[INFO] Loading DEMNAS daratan: {os.path.basename(dem_path)}")
        dem_raw = tifffile.imread(dem_path)
        factors = (grid_size / dem_raw.shape[0], grid_size / dem_raw.shape[1])
        dem_rs = zoom(dem_raw, factors, order=2)
    else:
        print("[WARN] DEM tidak ditemukan — pakai terrain sintetis")
        return _make_synthetic_terrain(grid_size)

    # 2. Load BATNAS (Batimetri Laut Bawah Air)
    if os.path.exists(batnas_path) and HAS_SCIPY:
        import tifffile
        print(f"[INFO] Loading BATNAS batimetri: {os.path.basename(batnas_path)}")
        bat_raw = tifffile.imread(batnas_path)
        lats = np.linspace(DOMAIN['lat_max'], DOMAIN['lat_min'], grid_size)
        lons = np.linspace(DOMAIN['lon_min'], DOMAIN['lon_max'], grid_size)
        lons_g, lats_g = np.meshgrid(lons, lats)
        cols = (lons_g - 110.0) / 5.0 * 2999.0
        rows = (-5.0 - lats_g) / 5.0 * 2998.0
        bat_rs = map_coordinates(bat_raw, np.stack([rows, cols]), order=1)
        
        # Merge: di laut / batimetri (<0 atau lat < -8.35) gunakan BATNAS, di darat gunakan DEMNAS
        data_rs = np.where((bat_rs < 0) | (lats_g < -8.35), bat_rs, dem_rs)
        print(f"[INFO] Merged DEMNAS + BATNAS: {data_rs.shape}  "
              f"elev range: {data_rs.min():.0f}–{data_rs.max():.0f} m (MSL)")
    else:
        data_rs = np.clip(dem_rs, 0, 4000)
        data_rs = enforce_ocean_flatness(data_rs, grid_size)
        
    return data_rs


def enforce_ocean_flatness(terrain_arr, grid_size=100):
    """Fallback jika BATNAS tidak ada: pastikan area lautan di selatan Jawa datar 0.0m"""
    lats = np.linspace(DOMAIN['lat_max'], DOMAIN['lat_min'], grid_size)
    for r, lat in enumerate(lats):
        if lat < -8.48:
            terrain_arr[r, :] = 0.0
        elif lat < -8.35:
            factor = (lat - (-8.48)) / (-8.35 - (-8.48))
            terrain_arr[r, :] *= np.clip(factor, 0.0, 1.0)
    return terrain_arr


def _make_synthetic_terrain(grid_size=100):
    """Buat terrain sintetis mirip Tulungagung (gunung di utara, pantai selatan)"""
    print("[INFO] Membuat terrain sintetis (Tulungagung-like)...")
    x = np.linspace(-1, 1, grid_size)
    y = np.linspace(-1, 1, grid_size)
    X, Y = np.meshgrid(x, y)

    # Pantai selatan (Y=-1), Gunung Wilis di utara-barat
    base = 100 * (1 - Y)   # lereng utara lebih tinggi
    wilis = 2500 * np.exp(-((X + 0.4)**2 + (Y - 0.5)**2) / 0.08)
    hills = 800  * np.exp(-((X - 0.2)**2 + (Y + 0.1)**2) / 0.15)
    coast = -50  * np.exp(-((Y + 0.9)**2) / 0.02)
    noise = 50   * np.random.RandomState(42).randn(*X.shape)
    noise = gaussian_filter(noise, sigma=3)

    terrain = np.clip(base + wilis + hills + coast + noise, 0, 3500)
    terrain = enforce_ocean_flatness(terrain, grid_size)
    print(f"[INFO] Sintetis terrain: {terrain.min():.0f}–{terrain.max():.0f} m")
    return terrain


def wind_height_extrapolation(u_10, v_10, target_heights_m,
                               roughness_z0=0.03, ref_height=10.0):
    """
    Ekstrapolasi angin dari 10m AGL ke berbagai ketinggian
    menggunakan logarithmic wind profile.
    z0 = roughness length: 0.03 m (open terrain/coastal)
    """
    results = {}
    for h in target_heights_m:
        factor = np.log(h / roughness_z0) / np.log(ref_height / roughness_z0)
        results[h] = {
            'u': u_10 * factor,
            'v': v_10 * factor,
        }
        results[h]['wspd'] = np.sqrt(results[h]['u']**2 + results[h]['v']**2)
        results[h]['wpd']  = 0.5 * AIR_RHO * results[h]['wspd']**3
    return results


def regrid_wind_to_dem(wind_data, target_grid_size, lats_era5, lons_era5):
    """Interpolasi wind grid ERA5 ke resolusi grid DEM"""
    from scipy.interpolate import RegularGridInterpolator

    # ERA5 lat descending (dari utara ke selatan)
    lats_asc = lats_era5[::-1]  # ascending untuk interp
    target_lats = np.linspace(DOMAIN['lat_min'], DOMAIN['lat_max'], target_grid_size)
    target_lons = np.linspace(DOMAIN['lon_min'], DOMAIN['lon_max'], target_grid_size)

    regridded = {}
    for h, vars_h in wind_data.items():
        regridded[h] = {}
        for vname in ['u', 'v', 'wspd']:
            arr = vars_h[vname]
            # Flip jika lat descending
            if lats_era5[0] > lats_era5[-1]:
                arr = arr[::-1, :]

            interp = RegularGridInterpolator(
                (lats_asc, lons_era5), arr,
                method='linear', bounds_error=False, fill_value=np.nanmean(arr)
            )
            pts = np.array([(la, lo)
                            for la in target_lats for lo in target_lons])
            regridded[h][vname] = interp(pts).reshape(target_grid_size, target_grid_size)
    return regridded, target_lats, target_lons


def build_json(terrain, wind_layers_gridded, lats, lons, stats, out_path):
    """Build dan simpan wind_data.json untuk Three.js"""
    print("[INFO] Building wind_data.json...")
    NX = terrain.shape[1]
    NZ = terrain.shape[0]

    # Normalisasi terrain agar 0.0 = Permukaan Laut (MSL 0m) dan 1.0 = Puncak Tertinggi (t_max)
    # Kedalaman laut (t < 0) bernilai negatif, e.g. -0.5 untuk -1300m
    t_min, t_max = float(terrain.min()), float(terrain.max())
    scale_max = max(t_max, 1.0)
    terrain_norm = (terrain / scale_max).tolist()

    wind_layers_out = []
    for h, data_h in wind_layers_gridded.items():
        u_flat  = data_h['u'].tolist()
        v_flat  = data_h['v'].tolist()
        w_flat  = (np.zeros_like(data_h['u'])).tolist()  # W=0 untuk ERA5 (no vertical)
        ws_flat = data_h['wspd'].tolist()
        wpd_flat = (0.5 * 1.225 * (data_h['wspd'] ** 3)).tolist()
        wind_layers_out.append({
            'agl':   int(h),
            'u':     u_flat,
            'v':     v_flat,
            'w':     w_flat,
            'wspd':  ws_flat,
            'wpd':   wpd_flat,
        })

    data = {
        'meta': {
            'nx': NX, 'nz': NZ,
            'n_levels': len(LEVELS_M),
            'levels_m_agl': LEVELS_M,
            'lon_min': float(lons.min()), 'lon_max': float(lons.max()),
            'lat_min': float(lats.min()), 'lat_max': float(lats.max()),
            'elev_min_m': float(t_min), 'elev_max_m': float(t_max),
            'data_source': 'ERA5 1980-2025 (10m AGL extrapolated)',
            'center': {'lat': NIYAMA['lat'], 'lon': NIYAMA['lon']},
        },
        'terrain':     terrain_norm,
        'wind_layers': wind_layers_out,
        'stats':       stats,
    }

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w') as f:
        json.dump(data, f, separators=(',', ':'))   # compact untuk ukuran kecil
    
    try:
        proc_dir = os.path.join(BASE_DIR, 'Data', 'processed')
        os.makedirs(proc_dir, exist_ok=True)
        proc_path = os.path.join(proc_dir, 'wind_data.json')
        with open(proc_path, 'w') as f:
            json.dump(data, f, separators=(',', ':'))
        print(f"[DONE] JSON also copied to: {proc_path}")
    except Exception as e:
        print(f"[WARN] Gagal menyalin ke Data/processed: {e}")

    size_mb = os.path.getsize(out_path) / 1e6
    print(f"[DONE] JSON saved: {out_path}  ({size_mb:.2f} MB)")
    if size_mb > 5:
        print(f"[WARN] File > 5MB — pertimbangkan kurangi GRID_SIZE atau kompres")
    return size_mb


# ── MAIN ────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    print("=" * 65)
    print("  TAHAP 4 — ERA5 + DEM → wind_data.json")
    print("=" * 65)

    # ── 1. Load ERA5 ────────────────────────────────────────────────────
    era5 = load_era5_mean_wind(DATA_DIR, FILE_HEAD)

    # ── 2. Load DEM ────────────────────────────────────────────────────
    terrain = load_dem_resampled(DEM_PATH, grid_size=GRID_SIZE)

    # ── 3. Ekstrapolasi angin ke 3 level ketinggian ─────────────────────
    print(f"[INFO] Ekstrapolasi angin ke {LEVELS_M} m AGL...")
    wind_h = wind_height_extrapolation(
        era5['u_mean'], era5['v_mean'], LEVELS_M
    )
    wind_h_p75 = wind_height_extrapolation(
        era5['u_p75'], era5['v_p75'], LEVELS_M
    )
    wind_h_p90 = wind_height_extrapolation(
        era5['u_p90'], era5['v_p90'], LEVELS_M
    )

    # ── 4. Regrid ke resolusi DEM grid ──────────────────────────────────
    if HAS_SCIPY:
        print(f"[INFO] Regrid wind → {GRID_SIZE}x{GRID_SIZE} grid...")
        wind_gridded, target_lats, target_lons = regrid_wind_to_dem(
            wind_h, GRID_SIZE, era5['lats'], era5['lons']
        )
    else:
        print("[WARN] scipy tidak ada — wind grid tidak di-resample")
        wind_gridded = {}
        for h, d in wind_h.items():
            wind_gridded[h] = {k: np.resize(v, (GRID_SIZE, GRID_SIZE))
                               for k, v in d.items()}
        target_lats = np.linspace(DOMAIN['lat_min'], DOMAIN['lat_max'], GRID_SIZE)
        target_lons = np.linspace(DOMAIN['lon_min'], DOMAIN['lon_max'], GRID_SIZE)

    # ── 5. Hitung statistik ringkas ─────────────────────────────────────
    ws_100 = wind_gridded.get(100, {}).get('wspd', np.array([[0]]))
    stats = {
        'wspd_mean_100m': float(np.nanmean(ws_100)),
        'wspd_p75_100m':  float(np.nanpercentile(ws_100, 75)),
        'wspd_p90_100m':  float(np.nanpercentile(ws_100, 90)),
        'wpd_mean_100m':  float(np.nanmean(0.5 * AIR_RHO * ws_100**3)),
    }
    print(f"\n  Statistik angin di 100m AGL:")
    for k, v in stats.items():
        print(f"    {k}: {v:.3f}")

    # ── 6. Build JSON ────────────────────────────────────────────────────
    build_json(terrain, wind_gridded, target_lats, target_lons, stats, OUT_JSON)

    # ── 7. Update data_bundle.js otomatis ────────────────────────────────
    try:
        from make_data_bundle import make_bundle
        make_bundle()
    except Exception as e:
        print(f"[WARN] Gagal update data_bundle.js otomatis: {e}")

    print(f"\n[DONE] Tahap 4 selesai — JSON & Bundle siap untuk visualisasi")
