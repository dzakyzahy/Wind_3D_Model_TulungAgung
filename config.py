"""
config.py — Konfigurasi sentral Wind Resource Assessment Tulungagung (PLN)
===========================================================================
Import di setiap script:
    import sys
    sys.path.insert(0, r"D:\ITB2\Pak_RK\MetOcean_Tulungagung\kode_zahy\WindModel3DProject")
    import config as cfg
"""
import os, sys
if hasattr(sys, 'stdout') and hasattr(sys.stdout, 'reconfigure'):
    try: sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass
if hasattr(sys, 'stderr') and hasattr(sys.stderr, 'reconfigure'):
    try: sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass

# ── Root Proyek ─────────────────────────────────────────────────────────────
ROOT = r"D:\ITB2\Pak_RK\MetOcean_Tulungagung\kode_zahy\WindModel3DProject"

# ── Direktori Data ───────────────────────────────────────────────────────────
# ERA5 per-variabel per-tahun ada di Data\era5\ (folder kode_zahy\WindModel3DProject)
DIR_ERA5_SL  = os.path.join(ROOT, "Data", "era5")          # ERA5_*_u10_*.nc dll
DIR_ERA5_PL  = os.path.join(ROOT, "Data", "era5")          # pressure level (jika ada)
DIR_ERA5_MSS = os.path.join(ROOT, "Data", "era5_missing")  # file hilang

# ERA5 dari folder Data utama (data_zahy)
DIR_ERA5_MAIN = r"D:\ITB2\Pak_RK\MetOcean_Tulungagung\Data\data_zahy"

DIR_DEMNAS   = os.path.join(ROOT, "Data", "Demnas")         # 12 tile DEMNAS_*.tif
DIR_DEM_PROC = os.path.join(ROOT, "Data", "Demnas", "processed")
DIR_OBS      = os.path.join(ROOT, "Data", "bmkg")           # observasi BMKG
DIR_PROC     = os.path.join(ROOT, "Data", "processed")      # output intermediate
DIR_OUTPUT   = os.path.join(ROOT, "processing", "output")   # PNG, PDF, JSON
DIR_VIZ      = os.path.join(ROOT, "visualization")          # HTML + JSON browser

# ── Parameter Domain ─────────────────────────────────────────────────────────
LAT_MIN, LAT_MAX = -9.29, -7.29
LON_MIN, LON_MAX = 110.8, 112.8

# ── Titik Kajian Utama ───────────────────────────────────────────────────────
SITE_LAT  = -8.292
SITE_LON  = 111.797
SITE_NAME = "Niyama Beach, Tulungagung"

# ── Parameter Angin ──────────────────────────────────────────────────────────
HUB_HEIGHTS    = [50, 80, 100, 150]   # meter AGL
ALPHA_ONSHORE  = 0.20                 # power law exponent onshore
ALPHA_OFFSHORE = 0.14                 # power law exponent offshore
Z_REF          = 10.0                 # ketinggian referensi ERA5 (m)
RHO_AIR        = 1.225                # densitas udara kg/m³
Z0_ERA5        = 0.03                 # roughness length ERA5 default (grassland) m
Z0_COAST       = 0.001                # roughness length pantai m
Z0_FOREST      = 0.5                  # roughness length hutan m

# ── Parameter Turbin Vestas V150-4.5MW (IEC Class III) ───────────────────────
ROTOR_DIAMETER  = 150.0               # meter
HUB_HEIGHT_REF  = 100.0               # meter
P_RATED         = 4500.0              # kW
CT              = 0.8                 # thrust coefficient (adimensional)
WAKE_K_ONSHORE  = 0.05               # wake decay constant onshore
WAKE_K_OFFSHORE = 0.04               # wake decay constant offshore

# Power curve Vestas V150-4.5MW (m/s → kW)
# cut-in 3 m/s, rated 12 m/s, cut-out 25 m/s
POWER_CURVE = {
    0:  0,   1:  0,   2:  0,   3:  50,
    4:  185, 5:  400, 6:  720, 7: 1100,
    8: 1600, 9: 2150, 10: 2800, 11: 3500,
    12: 4200, 13: 4400, 14: 4450, 15: 4500,
    16: 4500, 17: 4500, 18: 4500, 19: 4500,
    20: 4500, 21: 4500, 22: 4500, 23: 4500,
    24: 4500, 25: 4500, 26: 0,
}

# ── Logo PLN ─────────────────────────────────────────────────────────────────
LOGO_PLN = os.path.join(ROOT, "Logo_PLN.png")

# ── Threshold Extreme Wind ───────────────────────────────────────────────────
EXTREME_WS_THRESHOLD = 17.0   # m/s @ 100m → IEC extreme
EXTREME_DIR_CHANGE   = 45.0   # derajat per jam → EWD event

# ── Pola file ERA5 (sesuai data_zahy) ───────────────────────────────────────
ERA5_U10_PATTERN = "ERA5_Tulungagung_1hr_0125_u10_{year}.nc"
ERA5_V10_PATTERN = "ERA5_Tulungagung_1hr_0125_v10_{year}.nc"
ERA5_VAR_U10 = "u10"
ERA5_VAR_V10 = "v10"
ERA5_START_YEAR = 1980
ERA5_END_YEAR   = 2025

# ── Buat folder yang belum ada saat import ───────────────────────────────────
_dirs_to_create = [
    DIR_ERA5_SL, DIR_ERA5_MSS, DIR_DEM_PROC,
    DIR_PROC, DIR_OUTPUT, DIR_VIZ,
    os.path.join(ROOT, "Data", "srtm"),
]
for _d in _dirs_to_create:
    os.makedirs(_d, exist_ok=True)

if __name__ == "__main__":
    print("=" * 60)
    print("  Wind Resource Assessment — Konfigurasi Proyek")
    print("=" * 60)
    print(f"  ROOT     : {ROOT}")
    print(f"  ERA5 main: {DIR_ERA5_MAIN}")
    print(f"  DEMNAS   : {DIR_DEMNAS}")
    print(f"  Output   : {DIR_OUTPUT}")
    print(f"  Viz      : {DIR_VIZ}")
    print(f"  Site     : {SITE_NAME} ({SITE_LAT}, {SITE_LON})")
    print(f"  Domain   : [{LAT_MIN},{LAT_MAX}] × [{LON_MIN},{LON_MAX}]")
    print(f"  Hub Hts  : {HUB_HEIGHTS} m")
    import glob
    tif_files = glob.glob(os.path.join(DIR_DEMNAS, "DEMNAS_*.tif"))
    u10_files = glob.glob(os.path.join(DIR_ERA5_MAIN, "ERA5_*_u10_*.nc"))
    print(f"  DEMNAS tiles found : {len(tif_files)}")
    print(f"  ERA5 u10 files found: {len(u10_files)}")
    print("[DONE] Modul 0.C — config.py terverifikasi")
