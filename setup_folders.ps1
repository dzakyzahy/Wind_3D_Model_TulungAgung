# setup_folders.ps1 - Buat struktur folder WindModel3DProject
# Jalankan di PowerShell: .\setup_folders.ps1

$root = "D:\ITB2\Pak_RK\MetOcean_Tulungagung\kode_zahy\WindModel3DProject"

$folders = @(
    "Data\era5",
    "Data\era5_missing",
    "Data\Demnas\processed",
    "Data\bmkg",
    "Data\srtm",
    "Data\processed",
    "processing\scripts",
    "processing\output",
    "visualization"
)

foreach ($f in $folders) {
    $path = Join-Path $root $f
    if (-not (Test-Path $path)) {
        New-Item -ItemType Directory -Force -Path $path | Out-Null
        Write-Host "[CREATE] $path" -ForegroundColor Green
    } else {
        Write-Host "[EXISTS] $path" -ForegroundColor Gray
    }
}

Write-Host ""
Write-Host "Struktur folder berhasil disiapkan di:" -ForegroundColor Cyan
Write-Host $root -ForegroundColor Yellow

# Verifikasi file data penting
Write-Host ""
Write-Host "Verifikasi data:" -ForegroundColor Cyan
$era5_main = "D:\ITB2\Pak_RK\MetOcean_Tulungagung\Data\data_zahy"
$demnas_dir = Join-Path $root "Data\Demnas"

$u10_count = (Get-ChildItem "$era5_main\ERA5_*_u10_*.nc" -ErrorAction SilentlyContinue).Count
$tif_count = (Get-ChildItem "$demnas_dir\DEMNAS_*.tif" -ErrorAction SilentlyContinue).Count

Write-Host "  ERA5 u10 files : $u10_count (di $era5_main)" -ForegroundColor White
Write-Host "  DEMNAS tiles   : $tif_count (di $demnas_dir)" -ForegroundColor White

if ($u10_count -gt 0) {
    Write-Host "  [OK] ERA5 data tersedia" -ForegroundColor Green
} else {
    Write-Host "  [WARN] ERA5 tidak ditemukan - pipeline akan pakai demo data" -ForegroundColor Yellow
}

if ($tif_count -gt 0) {
    Write-Host "  [OK] DEMNAS tersedia" -ForegroundColor Green
} else {
    Write-Host "  [WARN] DEMNAS tidak ditemukan - pipeline akan pakai DEM sintetis" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "[DONE] Modul 0.A - setup_folders.ps1 selesai" -ForegroundColor Green
