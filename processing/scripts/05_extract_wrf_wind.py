"""
05_extract_wrf_wind.py — Ekstraksi angin 3D dari output WRF

Input  : wrf/output/wrfout_d03_*
Output : processing/output/wind_3d_extracted.nc

CATATAN: Script ini hanya bisa dijalankan SETELAH wrf.exe selesai.
         Untuk demo sebelum WRF siap, script 04 sudah pakai ERA5 langsung.

Run: python processing/scripts/05_extract_wrf_wind.py
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
    from wrf import getvar, ALL_TIMES, interplevel, destagger, to_np
    HAS_WRF = True
except ImportError:
    HAS_WRF = False
    print("[WARN] wrf-python tidak ada — pip install wrf-python")
    print("       Akan coba manual extraction sebagai fallback...")

try:
    from netCDF4 import Dataset
    HAS_NC4 = True
except ImportError:
    HAS_NC4 = False

# ── Paths ───────────────────────────────────────────────────────────────────
BASE_DIR   = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WRF_OUT    = os.path.join(BASE_DIR, 'wrf', 'output')
OUT_DIR    = os.path.join(BASE_DIR, 'processing', 'output')
OUT_NC     = os.path.join(OUT_DIR, 'wind_3d_extracted.nc')
TARGET_AGL = [50, 100, 200]   # 3 ketinggian AGL target

os.makedirs(OUT_DIR, exist_ok=True)


def find_wrfout(wrf_dir, domain='d03'):
    """Cari semua file wrfout domain tertentu"""
    pattern = os.path.join(wrf_dir, f'wrfout_{domain}_*')
    files   = sorted(glob.glob(pattern))
    if not files:
        raise FileNotFoundError(
            f"Tidak ada file wrfout_{domain}_* di {wrf_dir}\n"
            f"Pastikan WRF sudah selesai dijalankan!"
        )
    print(f"[INFO] Ditemukan {len(files)} file wrfout_{domain}")
    return files


def extract_wind_wrfpython(files):
    """Ekstraksi menggunakan wrf-python (preferred)"""
    print("[INFO] Ekstraksi menggunakan wrf-python...")
    ds_list = [Dataset(f) for f in files]

    u_all, v_all, w_all, z_all, hgt_all = [], [], [], [], []
    times_all = []

    for ds in ds_list:
        # Variabel staggered
        u_raw = getvar(ds, 'U', timeidx=ALL_TIMES, meta=False)   # staggered X
        v_raw = getvar(ds, 'V', timeidx=ALL_TIMES, meta=False)   # staggered Y
        w_raw = getvar(ds, 'W', timeidx=ALL_TIMES, meta=False)   # staggered Z
        ph    = getvar(ds, 'PH',  timeidx=ALL_TIMES, meta=False)
        phb   = getvar(ds, 'PHB', timeidx=ALL_TIMES, meta=False)
        hgt   = getvar(ds, 'HGT', timeidx=ALL_TIMES, meta=False)

        # Destagger
        u = destagger(u_raw, stagger_dim=-1)
        v = destagger(v_raw, stagger_dim=-2)
        w = destagger(w_raw, stagger_dim=-3)

        # Ketinggian (m) — geopotential ke meter
        z_full = (ph + phb) / 9.81   # total geopotential height MSL
        z_agl  = destagger(z_full, stagger_dim=-3) - hgt[..., np.newaxis, :, :]

        u_all.append(u); v_all.append(v); w_all.append(w)
        z_all.append(z_agl); hgt_all.append(hgt)

        try:
            times = getvar(ds, 'Times', timeidx=ALL_TIMES, meta=False)
            times_all.extend(times)
        except Exception:
            pass

    for ds in ds_list:
        ds.close()

    U = np.concatenate(u_all, axis=0)
    V = np.concatenate(v_all, axis=0)
    W = np.concatenate(w_all, axis=0)
    Z = np.concatenate(z_all, axis=0)
    HGT = hgt_all[0]  # terrain height tidak berubah

    return U, V, W, Z, HGT, times_all


def extract_wind_manual(files):
    """Fallback: ekstraksi manual tanpa wrf-python"""
    print("[INFO] Ekstraksi manual (tanpa wrf-python)...")
    u_all, v_all, w_all, z_all, hgt = [], [], [], [], None

    for f in files:
        ds = xr.open_dataset(f)
        # U staggered → destagger manual
        U_s = ds['U'].values     # (time, bottom_top, south_north, west_east_stag)
        V_s = ds['V'].values     # (time, bottom_top, south_north_stag, west_east)
        W_s = ds['W'].values     # (time, bottom_top_stag, south_north, west_east)
        PH  = ds['PH'].values
        PHB = ds['PHB'].values
        HGT_v = ds['HGT'].values[0]  # (south_north, west_east)

        # Simple destagger (average adjacent)
        U = 0.5 * (U_s[..., :-1] + U_s[..., 1:])
        V = 0.5 * (V_s[:, :, :-1, :] + V_s[:, :, 1:, :])
        W = 0.5 * (W_s[:, :-1, :, :] + W_s[:, 1:, :, :])
        Z_full = (PH + PHB) / 9.81
        Z_agl  = 0.5*(Z_full[:, :-1, :, :] + Z_full[:, 1:, :, :]) - HGT_v[np.newaxis, np.newaxis, :, :]

        u_all.append(U); v_all.append(V); w_all.append(W); z_all.append(Z_agl)
        if hgt is None:
            hgt = HGT_v
        ds.close()

    U = np.concatenate(u_all, axis=0)
    V = np.concatenate(v_all, axis=0)
    W = np.concatenate(w_all, axis=0)
    Z = np.concatenate(z_all, axis=0)
    return U, V, W, Z, hgt, []


def interp_to_agl(U, V, W, Z, target_m):
    """Interpolasi vertikal ke ketinggian AGL target (meter)"""
    ntime, nlev, nlat, nlon = U.shape
    u_out = np.full((ntime, nlat, nlon), np.nan)
    v_out = np.full((ntime, nlat, nlon), np.nan)
    w_out = np.full((ntime, nlat, nlon), np.nan)

    for t in range(ntime):
        for j in range(nlat):
            for i in range(nlon):
                z_col = Z[t, :, j, i]
                u_col = U[t, :, j, i]
                v_col = V[t, :, j, i]
                w_col = W[t, :, j, i]
                if np.isfinite(z_col).all():
                    u_out[t, j, i] = np.interp(target_m, z_col, u_col)
                    v_out[t, j, i] = np.interp(target_m, z_col, v_col)
                    w_out[t, j, i] = np.interp(target_m, z_col, w_col)
    return u_out, v_out, w_out


def save_netcdf(U_dict, V_dict, W_dict, HGT, times, out_path):
    """Simpan hasil ke NetCDF ringkas"""
    import xarray as xr
    ds_dict = {}
    for h in TARGET_AGL:
        u = U_dict[h]; v = V_dict[h]; w = W_dict[h]
        wspd = np.sqrt(u**2 + v**2)
        ds_dict[f'U_{h}m']    = xr.DataArray(u,    dims=['time','lat','lon'])
        ds_dict[f'V_{h}m']    = xr.DataArray(v,    dims=['time','lat','lon'])
        ds_dict[f'W_{h}m']    = xr.DataArray(w,    dims=['time','lat','lon'])
        ds_dict[f'WSPD_{h}m'] = xr.DataArray(wspd, dims=['time','lat','lon'])
        # Time mean
        ds_dict[f'WSPD_{h}m_MEAN'] = xr.DataArray(np.nanmean(wspd, axis=0), dims=['lat','lon'])
        ds_dict[f'WSPD_{h}m_P75']  = xr.DataArray(np.nanpercentile(wspd, 75, axis=0), dims=['lat','lon'])
        ds_dict[f'WSPD_{h}m_P90']  = xr.DataArray(np.nanpercentile(wspd, 90, axis=0), dims=['lat','lon'])

    ds_dict['HGT'] = xr.DataArray(HGT, dims=['lat','lon'])
    ds = xr.Dataset(ds_dict)
    ds.attrs['description'] = 'WRF-ARW D03 3km wind extraction — Tulungagung'
    ds.attrs['levels_m_agl'] = str(TARGET_AGL)
    ds.to_netcdf(out_path)
    print(f"[DONE] Saved: {out_path}  ({os.path.getsize(out_path)/1e6:.1f} MB)")


# ── MAIN ────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    print("=" * 65)
    print("  TAHAP 5 — Ekstraksi Angin dari WRF Output")
    print("=" * 65)

    files = find_wrfout(WRF_OUT, domain='d03')

    if HAS_WRF:
        U, V, W, Z, HGT, times = extract_wind_wrfpython(files)
    else:
        U, V, W, Z, HGT, times = extract_wind_manual(files)

    print(f"[INFO] Data shape: U={U.shape}  Z range: {Z.min():.0f}–{Z.max():.0f} m AGL")

    # Interpolasi ke 3 level AGL
    U_dict, V_dict, W_dict = {}, {}, {}
    for h in TARGET_AGL:
        print(f"[INFO] Interpolasi ke {h}m AGL...")
        u_h, v_h, w_h = interp_to_agl(U, V, W, Z, h)
        U_dict[h] = u_h; V_dict[h] = v_h; W_dict[h] = w_h
        wspd_mean = np.nanmean(np.sqrt(u_h**2 + v_h**2))
        print(f"       Mean wind speed: {wspd_mean:.2f} m/s")

    save_netcdf(U_dict, V_dict, W_dict, HGT, times, OUT_NC)
    print(f"\n[DONE] Tahap 5 selesai → {OUT_NC}")
    print("       Lanjutkan dengan: python processing/scripts/06_wrf_to_json.py")
