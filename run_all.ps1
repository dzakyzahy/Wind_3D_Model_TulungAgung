################################################################################
# run_all.ps1 - Pipeline Wind Resource Assessment Tulungagung
# Menjalankan Modul 0-8 secara berurutan
# Gunakan: conda activate wind_pln; .\run_all.ps1
################################################################################

$ProjectRoot = "D:\ITB2\Pak_RK\MetOcean_Tulungagung\kode_zahy\WindModel3DProject"
$Scripts     = Join-Path $ProjectRoot "processing\scripts"
$StartTime   = Get-Date
$OK          = @()
$FAIL        = @()

Write-Host ""
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host " Wind Resource Assessment Pipeline - Tulungagung, Jawa Timur" -ForegroundColor Cyan
Write-Host " $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Gray
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host ""

function Run-Module {
    param([string]$Script, [string]$Label)
    $path = Join-Path $Scripts $Script
    if (-not (Test-Path $path)) {
        Write-Host " [SKIP] $Label - $Script tidak ditemukan" -ForegroundColor Yellow
        return
    }
    Write-Host " >> Menjalankan $Label..." -ForegroundColor White
    $t0 = Get-Date
    python $path
    if ($LASTEXITCODE -eq 0) {
        $elapsed = (Get-Date) - $t0
        Write-Host " [OK] $Label selesai dalam $($elapsed.TotalSeconds.ToString('F1'))s" -ForegroundColor Green
        $script:OK += $Label
    } else {
        Write-Host " [ERROR] $Label gagal (exit code $LASTEXITCODE)" -ForegroundColor Red
        $script:FAIL += $Label
    }
    Write-Host ""
}

# -- Setup folders --------------------------------------------------------------
Write-Host " >> Menyiapkan folder project..." -ForegroundColor White
$setupScript = Join-Path $ProjectRoot "setup_folders.ps1"
if (Test-Path $setupScript) {
    & $setupScript
} else {
    Write-Host " [WARN] setup_folders.ps1 tidak ditemukan - lewati" -ForegroundColor Yellow
}
Write-Host ""

# -- Modules -------------------------------------------------------------------
Run-Module "01_mosaic_dem.py"       "Modul 1 - DEM Mosaik DEMNAS"
Run-Module "02_wind_climate.py"     "Modul 2 - Wind Climate ERA5"
Run-Module "03_topo_correction.py"  "Modul 3 - Koreksi Topografi (Jackson-Hunt)"
Run-Module "04_wake_analysis.py"    "Modul 4 - Wake Effect (Jensen/Park)"
Run-Module "05_extreme_wind.py"     "Modul 5 - Angin Ekstrem (Gumbel)"
Run-Module "06_nc_to_json.py"       "Modul 6 - Konsolidasi JSON Browser"
Run-Module "08_generate_report.py"  "Modul 8 - Laporan PDF"

# -- Summary -------------------------------------------------------------------
$TotalElapsed = (Get-Date) - $StartTime
Write-Host ""
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host " RINGKASAN PIPELINE" -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host " Total waktu   : $($TotalElapsed.TotalMinutes.ToString('F1')) menit" -ForegroundColor White
Write-Host " Modul berhasil: $($OK.Count)" -ForegroundColor Green
foreach ($m in $OK)   { Write-Host "   [OK] $m" -ForegroundColor Green }
if ($FAIL.Count -gt 0) {
    Write-Host " Modul gagal   : $($FAIL.Count)" -ForegroundColor Red
    foreach ($m in $FAIL) { Write-Host "   [FAIL] $m" -ForegroundColor Red }
}
Write-Host ""

# -- Output files --------------------------------------------------------------
$OutputDir = Join-Path $ProjectRoot "output"
$PdfPath   = Join-Path $OutputDir "WindReport_Tulungagung_PLN.pdf"
$VizPath   = Join-Path $ProjectRoot "visualization"

Write-Host " Output utama:" -ForegroundColor Cyan
if (Test-Path $PdfPath)            { Write-Host "   [PDF]  $PdfPath" -ForegroundColor White }
Write-Host "   [3D]   $VizPath\index.html (Three.js 3D)" -ForegroundColor White
Write-Host "   [DASH] $VizPath\dashboard.html (Plotly Dashboard)" -ForegroundColor White
Write-Host ""
Write-Host "  -> Buka dashboard: Start-Process '$VizPath\dashboard.html'" -ForegroundColor Yellow
Write-Host "  -> Buka 3D viz  : Start-Process '$VizPath\index.html'" -ForegroundColor Yellow
Write-Host ""
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host " [DONE] Pipeline selesai" -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Cyan
