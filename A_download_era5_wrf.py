"""
A_download_era5_wrf.py — Download ERA5 untuk kebutuhan WRF Tulungagung
via Google Cloud Console → Google Drive (rclone)

CATATAN PENTING:
- Single Levels  : 1980–2026 (lengkap untuk analisis klimatologi)
- Pressure Levels: 2022 Jul–Agustus (periode simulasi WRF representatif)
                   BISA ditambah tahun lain setelah konfirmasi dosen

PRASYARAT:
  pip install cdsapi
  rclone configure  (setup gdrive remote bernama 'gdrive')
  export CDSAPI_KEY='your-uid:your-api-key'  # atau set di ~/.cdsapirc

Run: python A_download_era5_wrf.py
"""

import cdsapi
import os
import time

c = cdsapi.Client()

# ─── Parameter Geografis ────────────────────────────────────────────────────
# Format CDS: [North, West, South, East]
# Domain sama dengan E_helpers.py: lat [-9.29, -7.29], lon [110.8, 112.8]
area_bbox = [-7.29, 110.8, -9.29, 112.8]   # [N, W, S, E]
grid_res  = [0.25, 0.25]                    # 0.25° resolusi standar ERA5

# ─── rclone target (Google Drive folder) ───────────────────────────────────
rclone_target = "gdrive:PROJECT_WIND_3D_TULUNGAGUNG"

# Tanggal & jam
days  = [f"{d:02d}" for d in range(1, 32)]
times = [f"{h:02d}:00" for h in range(24)]

# ─── Variabel Single Level ─────────────────────────────────────────────────
# Dipecah 2 grup agar jumlah fields per request tidak melebihi batas CDS
vars_sl_group1 = [
    "surface_pressure",
    "mean_sea_level_pressure",
    "sea_surface_temperature",
    "snow_depth",
]

vars_sl_group2 = [
    "soil_temperature_level_1",
    "soil_temperature_level_2",
    "soil_temperature_level_3",
    "soil_temperature_level_4",
    "volumetric_soil_water_layer_1",
    "volumetric_soil_water_layer_2",
    "volumetric_soil_water_layer_3",
    "volumetric_soil_water_layer_4",
]

# ─── Pressure Levels ────────────────────────────────────────────────────────
# 26 level standar WRF — cukup tanpa kehilangan akurasi berarti
pressure_levels_wrf = [
    '1000', '975', '950', '925', '900',
    '850', '800', '750', '700', '650',
    '600', '550', '500', '450', '400',
    '350', '300', '250', '200', '150',
    '100', '70',  '50',  '30',  '20', '10'
]

vars_pl = [
    "u_component_of_wind",
    "v_component_of_wind",
    "temperature",
    "specific_humidity",
    "geopotential",
]


# ─── Helper Functions ────────────────────────────────────────────────────────
def move_to_drive(filename):
    """Upload file ke Google Drive via rclone dan hapus lokal"""
    print(f"   [UPLOAD] {filename} → {rclone_target} ...")
    ret = os.system(f"rclone move {filename} {rclone_target}")
    if ret != 0:
        print(f"   [WARN] rclone gagal untuk {filename} — file tetap di lokal.")
    else:
        print(f"   [DONE] Upload selesai.")


def download_with_retry(dataset, request_params, output_file, max_retry=3):
    """Download CDS dengan retry otomatis jika gagal."""
    for attempt in range(1, max_retry + 1):
        try:
            c.retrieve(dataset, request_params, output_file)
            size_mb = os.path.getsize(output_file) / 1e6
            print(f"   [OK] Downloaded: {output_file} ({size_mb:.1f} MB)")
            return True
        except Exception as e:
            print(f"   [ERROR] Attempt {attempt}/{max_retry} gagal: {e}")
            if attempt < max_retry:
                wait = 60 * attempt
                print(f"   Menunggu {wait}s sebelum retry...")
                time.sleep(wait)
    return False


# ═══════════════════════════════════════════════════════════════════════════
# BAGIAN 1: SINGLE LEVELS (1980–2026)
# Dibutuhkan untuk: analisis klimatologi + WRF boundary
# Estimasi ukuran total: ~200–400 GB (tergantung kompresi server)
# ═══════════════════════════════════════════════════════════════════════════
print("=" * 65)
print("BAGIAN 1: SINGLE LEVELS (1980–2026)")
print("Tujuan: sp, msl, sst, soil vars, snow_depth untuk WRF BC")
print("=" * 65)

for year in range(1980, 2027):
    year_str = str(year)
    months = ['01', '02'] if year == 2026 else [f"{m:02d}" for m in range(1, 13)]

    for month in months:
        for grp_idx, vars_sl in enumerate([vars_sl_group1, vars_sl_group2], start=1):
            out_file = f"ERA5_SL_G{grp_idx}_{year_str}_{month}.nc"

            if os.path.exists(out_file):
                print(f"[SKIP] {out_file} (sudah ada)")
                continue

            print(f"\n[DL] Single Level Grp{grp_idx} | {year_str}-{month}")
            success = download_with_retry(
                'reanalysis-era5-single-levels',
                {
                    'product_type': 'reanalysis',
                    'variable':     vars_sl,
                    'year':         year_str,
                    'month':        month,
                    'day':          days,
                    'time':         times,
                    'area':         area_bbox,
                    'grid':         grid_res,
                    'format':       'netcdf',
                },
                out_file
            )

            if success:
                move_to_drive(out_file)
            else:
                print(f"[FAIL] {out_file} — gagal 3x, lanjut ke file berikutnya")

            time.sleep(5)   # jeda agar tidak rate-limited CDS


# ═══════════════════════════════════════════════════════════════════════════
# BAGIAN 2: PRESSURE LEVELS (2024–2026 Feb)
#
# MENGAPA 2024–2026?
# → Data observasi CSV ITULUN2 tersedia: Des 2025 – Feb 2026
# → WRF disimulasikan pada periode yang SAMA agar bisa divalidasi
# → 2024 sebagai spin-up / perpanjangan untuk analisis musiman
# → Periode validasi utama: Des 2025 – Feb 2026 (monsun barat)
#
# Estimasi ukuran: ~40–60 GB total (2024 + 2025 + 2026 Jan-Feb)
# ═══════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 65)
print("BAGIAN 2: PRESSURE LEVELS (2024–2026)")
print("Tujuan: u,v,t,q,z untuk WRF BC — validasi vs ITULUN2 CSV")
print("Periode: 2024 full + 2025 full + 2026 Jan-Feb")
print("=" * 65)

# ── Konfigurasi periode pressure levels ──────────────────────────────────
# Periode: 2024–2026 (cocok dengan data validasi CSV ITULUN2 Des2025–Feb2026)
PL_YEAR_RANGE = range(2024, 2027)
PL_MONTHS_MAP = {
    2024: [f"{m:02d}" for m in range(1, 13)],   # semua bulan 2024
    2025: [f"{m:02d}" for m in range(1, 13)],   # semua bulan 2025 (termasuk Des)
    2026: ['01', '02'],                           # Jan–Feb 2026 (sesuai CSV)
}

for year in PL_YEAR_RANGE:
    year_str = str(year)
    months = PL_MONTHS_MAP.get(year, [f"{m:02d}" for m in range(1, 13)])

    for month in months:
        out_file = f"ERA5_PL_{year_str}_{month}.nc"

        if os.path.exists(out_file):
            print(f"[SKIP] {out_file} (sudah ada)")
            continue

        print(f"\n[DL] Pressure Levels | {year_str}-{month}")
        success = download_with_retry(
            'reanalysis-era5-pressure-levels',
            {
                'product_type':   'reanalysis',
                'variable':       vars_pl,
                'pressure_level': pressure_levels_wrf,
                'year':           year_str,
                'month':          month,
                'day':            days,
                'time':           times,
                'area':           area_bbox,
                'grid':           grid_res,
                'format':         'netcdf',
            },
            out_file
        )

        if success:
            move_to_drive(out_file)
        else:
            # Fallback: pecah per variabel
            print(f"[WARN] Request besar gagal — mencoba per variabel...")
            for var in vars_pl:
                var_short = (var.replace("_component_of_wind", "")
                               .replace("_", "")[:8])
                out_var = f"ERA5_PL_{var_short}_{year_str}_{month}.nc"

                if os.path.exists(out_var):
                    print(f"[SKIP] {out_var}")
                    continue

                success_var = download_with_retry(
                    'reanalysis-era5-pressure-levels',
                    {
                        'product_type':   'reanalysis',
                        'variable':       [var],
                        'pressure_level': pressure_levels_wrf,
                        'year':           year_str,
                        'month':          month,
                        'day':            days,
                        'time':           times,
                        'area':           area_bbox,
                        'grid':           grid_res,
                        'format':         'netcdf',
                    },
                    out_var
                )
                if success_var:
                    move_to_drive(out_var)
                else:
                    print(f"[FAIL] {out_var} — cek quota/koneksi CDS")

                time.sleep(5)

        time.sleep(5)


print("\n" + "=" * 65)
print("SELESAI! Periksa Google Drive folder:")
print(f"  {rclone_target}")
print("File gagal: cari [FAIL] di log di atas")
print("=" * 65)
