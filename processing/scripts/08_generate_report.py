"""
08_generate_report.py — Modul 8: Laporan PDF Profesional 9 Halaman
===================================================================
Output: cfg.DIR_OUTPUT\\WindReport_Tulungagung_PLN.pdf
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
import matplotlib.gridspec as gridspec
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import FancyBboxPatch, Rectangle

files_ok   = []
files_fail = []

DARK      = "#0a0e1a"
NAVY      = "#0d1b2a"
CYAN      = "#22d3ee"
GOLD      = "#f59e0b"
GREEN     = "#10b981"
RED       = "#ef4444"
LIGHT     = "#e0e8ff"
GRAY      = "#64748b"
MID_GRAY  = "#334155"
BLUE      = "#3b82f6"
PURPLE    = "#8b5cf6"
WHITE     = "#ffffff"

print("=" * 60)
print("[INFO] Modul 8 — PDF Report Generation")

# ══════════════════════════════════════════════════════════════════════════════
# Load data (dari JSON output Modul 1–5)
# ══════════════════════════════════════════════════════════════════════════════
def load_json(path, fallback=None):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    print(f"  [WARN] {os.path.basename(path)} tidak ditemukan — pakai dummy")
    return fallback

stats    = load_json(os.path.join(cfg.DIR_VIZ, "stats_summary.json"))
wake_d   = load_json(os.path.join(cfg.DIR_VIZ, "wake_data.json"))
extreme  = load_json(os.path.join(cfg.DIR_PROC, "extreme_wind_stats.json"))
weibull  = load_json(os.path.join(cfg.DIR_PROC, "weibull_params.json"))
wind_clim = load_json(os.path.join(cfg.DIR_PROC, "wind_climate.json"))

def safe(d, *keys, default="—"):
    try:
        v = d
        for k in keys: v = v[k]
        if v is None: return default
        if isinstance(v, float): return round(v, 3)
        return v
    except (TypeError, KeyError, IndexError):
        return default

IS_DEMO = (stats is None or stats.get("is_demo", True))

# ── Helpers nilai kunci ─────────────────────────────────────────────────────
wspd_100 = safe(stats,"wind_resource","wspd_mean_100m_ms", default=6.8)
wpd_100  = safe(stats,"wind_resource","wpd_mean_100m_wm2", default=185)
cf_100   = round(float(safe(stats,"wind_resource","cf_100m", default=0.28))*100, 1)
k_100    = safe(stats,"wind_resource","weibull_k_100m", default=2.1)
lam_100  = safe(stats,"wind_resource","weibull_lambda_100m", default=7.5)
v50      = safe(stats,"extreme_wind","v50_ms", default=28.0)
v_ref    = safe(stats,"extreme_wind","v_ref_ms", default=39.2)
iec_cls  = safe(stats,"extreme_wind","iec_class", default="III")
best_lay = safe(stats,"wake_and_farm","best_layout", default="B_grid_10D")
best_aep = safe(stats,"wake_and_farm","aep_gwh_yr", default=215)
best_wk  = safe(stats,"wake_and_farm","wake_loss_pct", default=5.0)
rekomendasi = safe(stats,"rekomendasi", default="Perlu kajian lebih lanjut")
trend_v  = safe(stats,"wind_resource","trend_ms_per_decade", default=0.0)

# ══════════════════════════════════════════════════════════════════════════════
# Fungsi utilitas plot
# ══════════════════════════════════════════════════════════════════════════════
def dark_fig(w=16, h=11):
    fig = plt.figure(figsize=(w, h), facecolor=DARK)
    return fig

def add_page_border(fig, title_text, page_num, total=9):
    """Tambah border dan header konsisten."""
    fig.text(0.5, 0.97, title_text, ha="center", va="top",
             fontsize=14, fontweight="bold", color=CYAN,
             fontfamily="DejaVu Sans")
    fig.text(0.5, 0.93, f"Kajian Sumber Daya Angin — {cfg.SITE_NAME} | PLN",
             ha="center", va="top", fontsize=9, color=GRAY)
    fig.text(0.97, 0.01, f"Halaman {page_num}/{total}", ha="right", va="bottom",
             fontsize=8, color=GRAY)
    fig.text(0.03, 0.01, f"Dihasilkan: {time.strftime('%Y-%m-%d')} | ERA5 1980–2025 | DEMNAS 8m",
             ha="left", va="bottom", fontsize=8, color=GRAY)
    if IS_DEMO:
        fig.text(0.5, 0.5, "DEMO MODE", ha="center", va="center",
                 fontsize=60, color=RED, alpha=0.06, fontweight="bold",
                 rotation=30)

# ══════════════════════════════════════════════════════════════════════════════
# Mulai PDF
# ══════════════════════════════════════════════════════════════════════════════
out_pdf = os.path.join(cfg.DIR_OUTPUT, "WindReport_Tulungagung_PLN.pdf")

with PdfPages(out_pdf) as pdf:
    print("[INFO] Membuat halaman 1 — Cover...")

    # ── Halaman 1: Cover ──────────────────────────────────────────────────────
    fig1 = dark_fig(16, 11)
    ax_cover = fig1.add_axes([0,0,1,1])
    ax_cover.set_xlim(0,1); ax_cover.set_ylim(0,1)
    ax_cover.axis("off"); ax_cover.set_facecolor(DARK)

    # Gradient background
    for i in range(100):
        t = i / 100
        col = (0.039*(1-t) + 0.05*t, 0.055*(1-t) + 0.08*t, 0.102*(1-t) + 0.18*t)
        ax_cover.add_patch(Rectangle((0, t*0.6), 1, 0.006, color=col, transform=ax_cover.transAxes))

    # Logo PLN
    if os.path.exists(cfg.LOGO_PLN):
        try:
            from PIL import Image
            logo = Image.open(cfg.LOGO_PLN)
            ax_logo = fig1.add_axes([0.04, 0.82, 0.1, 0.13])
            ax_logo.imshow(logo); ax_logo.axis("off")
        except Exception as e:
            print(f"  [WARN] Logo PLN gagal: {e}")
            ax_cover.text(0.08, 0.88, "⚡ PLN", ha="center", va="center",
                           fontsize=20, color=GOLD, fontweight="bold")
    else:
        ax_cover.text(0.08, 0.88, "⚡ PLN", ha="center", va="center",
                       fontsize=20, color=GOLD, fontweight="bold")

    # Judul utama
    ax_cover.text(0.5, 0.80, "KAJIAN SUMBER DAYA ANGIN", ha="center", va="center",
                   fontsize=28, color=WHITE, fontweight="bold", fontfamily="DejaVu Sans")
    ax_cover.text(0.5, 0.73, "Tulungagung, Jawa Timur", ha="center", va="center",
                   fontsize=22, color=CYAN, fontweight="bold")
    ax_cover.text(0.5, 0.67, "Wind Resource Assessment untuk PLTB", ha="center", va="center",
                   fontsize=15, color=LIGHT)

    # Garis pemisah
    ax_cover.plot([0.1, 0.9], [0.62, 0.62], color=CYAN, lw=2, alpha=0.8)
    ax_cover.plot([0.1, 0.9], [0.615, 0.615], color=GOLD, lw=0.5, alpha=0.6)

    # Info boxes
    boxes = [
        ("📡 Data Angin", "ERA5 ECMWF\n1980–2025\n0.125° Hourly"),
        ("🗺 DEM", "DEMNAS BIG\nResolusi 8m\n12 Tile"),
        ("📍 Lokasi", f"{cfg.SITE_NAME}\n{cfg.SITE_LAT}°S\n{cfg.SITE_LON}°E"),
        ("🌀 Turbin Ref.", "Vestas V150\n4.5 MW\nIEC Class III"),
    ]
    for i, (title, content) in enumerate(boxes):
        x = 0.1 + i * 0.21
        rect = FancyBboxPatch((x, 0.28), 0.18, 0.28,
                               boxstyle="round,pad=0.01",
                               facecolor=NAVY, edgecolor=CYAN,
                               linewidth=1.5, alpha=0.9)
        ax_cover.add_patch(rect)
        ax_cover.text(x+0.09, 0.52, title, ha="center", va="center",
                       fontsize=11, color=CYAN, fontweight="bold")
        ax_cover.text(x+0.09, 0.40, content, ha="center", va="center",
                       fontsize=9.5, color=LIGHT, linespacing=1.5)

    # Hasil kunci preview
    ax_cover.text(0.5, 0.25, "Hasil Kunci:", ha="center", va="center",
                   fontsize=12, color=GOLD, fontweight="bold")
    key_results = [
        f"Kecepatan Angin Rata-rata @100m: {wspd_100:.2f} m/s",
        f"Wind Power Density @100m: {wpd_100:.0f} W/m²",
        f"Capacity Factor: {cf_100:.1f}%",
        f"IEC Turbine Class: {iec_cls}",
    ]
    for i, txt in enumerate(key_results):
        ax_cover.text(0.5, 0.20 - i*0.05, txt, ha="center", va="center",
                       fontsize=10.5, color=LIGHT)

    ax_cover.text(0.5, 0.04, f"Tanggal Analisis: {time.strftime('%B %Y')} | Analisis berbasis ERA5 + DEMNAS + Statistical Downscaling",
                   ha="center", va="center", fontsize=8, color=GRAY)

    pdf.savefig(fig1, facecolor=DARK); plt.close(fig1)
    print("[DONE] Halaman 1 — Cover")

    # ── Halaman 2: Executive Summary ─────────────────────────────────────────
    print("[INFO] Membuat halaman 2 — Executive Summary...")
    fig2 = dark_fig()
    add_page_border(fig2, "Executive Summary — Rangkuman Hasil", 2)

    ax2 = fig2.add_axes([0.05, 0.08, 0.90, 0.80])
    ax2.set_facecolor(NAVY); ax2.axis("off")

    # Tabel parameter kunci
    params = [
        ("Parameter", "Nilai", "Satuan", "Keterangan"),
        ("Kecepatan angin rata-rata (100m)", str(round(float(str(wspd_100)),2)), "m/s", "Ekstrapolasi power law α=0.20"),
        ("Wind Power Density (100m)",        str(round(float(str(wpd_100)),1)),  "W/m²","Formula WPD standar IEC"),
        ("Capacity Factor estimasi",         f"{cf_100:.1f}", "%", "Vestas V150-4.5MW, Weibull integration"),
        ("Weibull k / λ (100m)",             f"{k_100:.3f} / {lam_100:.3f}", "— / m/s", "MLE fitting scipy.stats"),
        ("V50-year (100m)",                  str(round(float(str(v50)),1)), "m/s", "Gumbel distribution annual maxima"),
        ("V_ref IEC (= 1.4 × V50)",          str(round(float(str(v_ref)),1)), "m/s", "IEC 61400-1 standar"),
        ("IEC Wind Turbine Class",           f"Class {iec_cls}", "—", "Berdasarkan V_ref"),
        ("AEP layout terbaik (25 turbin)",   str(round(float(str(best_aep)),1)), "GWh/tahun", f"Layout {best_lay}"),
        ("Wake loss layout terbaik",         f"{round(float(str(best_wk)),1)}", "%", "Jensen/Park model"),
        ("Tren kecepatan angin",             f"{float(str(trend_v)):+.3f}", "m/s/dekade", "Linear regression ERA5"),
        ("Rekomendasi",                      rekomendasi, "—", "Berdasarkan IEC Class III threshold"),
    ]

    header = params[0]
    data_rows = params[1:]
    n_cols = len(header)
    col_x = [0.02, 0.35, 0.52, 0.62]
    col_w = [0.32, 0.16, 0.09, 0.38]

    # Header row
    for j, (hdr, cx) in enumerate(zip(header, col_x)):
        rect = Rectangle((cx, 0.88), col_w[j]-0.01, 0.08,
                           facecolor=CYAN+"22", edgecolor=CYAN, linewidth=0.8)
        ax2.add_patch(rect)
        ax2.text(cx+col_w[j]/2, 0.92, hdr, ha="center", va="center",
                  fontsize=10, color=CYAN, fontweight="bold")

    # Data rows
    for i, row in enumerate(data_rows):
        y = 0.82 - i * 0.065
        row_bg = NAVY if i % 2 == 0 else MID_GRAY+"44"
        for j, (cell, cx) in enumerate(zip(row, col_x)):
            rect = Rectangle((cx, y-0.03), col_w[j]-0.01, 0.058,
                               facecolor=row_bg, edgecolor=GRAY+"44", linewidth=0.3)
            ax2.add_patch(rect)
            cell_str = str(cell)
            color = LIGHT
            if j == 1:  # nilai kolom → warna spesial
                color = GOLD
            elif j == 0:
                color = LIGHT
            elif j == 3:
                color = GRAY
            ax2.text(cx+0.01 if j==0 else cx+col_w[j]/2,
                      y + 0.005,
                      cell_str, ha="left" if j==0 else "center",
                      va="center", fontsize=9 if j==3 else 10,
                      color=color,
                      wrap=True)

    # Highlight rekomendasi
    rec_color = GREEN if "Layak" in str(rekomendasi) else (GOLD if "Perlu" in str(rekomendasi) else RED)
    ax2.add_patch(FancyBboxPatch((0.02, 0.04), 0.96, 0.08,
                                  boxstyle="round,pad=0.005",
                                  facecolor=rec_color+"22",
                                  edgecolor=rec_color, linewidth=1.5))
    ax2.text(0.5, 0.08, f"REKOMENDASI: {rekomendasi}", ha="center", va="center",
              fontsize=11, color=rec_color, fontweight="bold")

    pdf.savefig(fig2, facecolor=DARK); plt.close(fig2)
    print("[DONE] Halaman 2 — Executive Summary")

    # ── Halaman 3: Peta Topografi ─────────────────────────────────────────────
    print("[INFO] Membuat halaman 3 — Peta Topografi...")
    fig3 = dark_fig()
    add_page_border(fig3, "Peta Topografi DEMNAS 8m — Domain Kajian", 3)

    out_dem_img = os.path.join(cfg.DIR_OUTPUT, "dem_mosaic_preview.png")
    if os.path.exists(out_dem_img):
        from PIL import Image
        img = np.array(Image.open(out_dem_img))
        ax3 = fig3.add_axes([0.05, 0.10, 0.90, 0.78])
        ax3.imshow(img); ax3.axis("off")
    else:
        ax3 = fig3.add_axes([0.05, 0.10, 0.90, 0.78])
        ax3.set_facecolor(NAVY)
        ax3.text(0.5, 0.5, "dem_mosaic_preview.png\n(Jalankan Modul 1 terlebih dahulu)",
                  ha="center", va="center", color=GRAY, fontsize=14,
                  transform=ax3.transAxes)
        ax3.axis("off")

    pdf.savefig(fig3, facecolor=DARK); plt.close(fig3)
    print("[DONE] Halaman 3 — Topografi")

    # ── Halaman 4: Wind Climate ───────────────────────────────────────────────
    print("[INFO] Membuat halaman 4 — Wind Climate...")
    fig4 = dark_fig()
    add_page_border(fig4, "Iklim Angin ERA5 1980–2025", 4)

    axes4_imgs = [
        ("windrose_annual.png", [0.04, 0.10, 0.44, 0.78]),
        ("wind_trend_timeseries.png", [0.52, 0.10, 0.46, 0.78]),
    ]
    for fname, pos in axes4_imgs:
        fpath = os.path.join(cfg.DIR_OUTPUT, fname)
        ax_i = fig4.add_axes(pos)
        if os.path.exists(fpath):
            from PIL import Image
            img = np.array(Image.open(fpath))
            ax_i.imshow(img); ax_i.axis("off")
        else:
            ax_i.set_facecolor(NAVY)
            ax_i.text(0.5, 0.5, fname+"\n(Jalankan Modul 2)", ha="center",
                       va="center", color=GRAY, fontsize=11, transform=ax_i.transAxes)
            ax_i.axis("off")

    pdf.savefig(fig4, facecolor=DARK); plt.close(fig4)
    print("[DONE] Halaman 4 — Wind Climate")

    # ── Halaman 5: Weibull + WPD Map ─────────────────────────────────────────
    print("[INFO] Membuat halaman 5 — Weibull + WPD...")
    fig5 = dark_fig()
    add_page_border(fig5, "Distribusi Weibull & Peta Wind Power Density", 5)

    for fname, pos in [("weibull_fit_site.png",[0.04,0.10,0.44,0.78]),
                        ("wpd_map_100m.png",   [0.52,0.10,0.46,0.78])]:
        fpath = os.path.join(cfg.DIR_OUTPUT, fname)
        ax_i = fig5.add_axes(pos)
        if os.path.exists(fpath):
            from PIL import Image
            img = np.array(Image.open(fpath))
            ax_i.imshow(img); ax_i.axis("off")
        else:
            ax_i.set_facecolor(NAVY)
            ax_i.text(0.5,0.5,fname+"\n(Modul 2)",ha="center",va="center",
                       color=GRAY,fontsize=11,transform=ax_i.transAxes)
            ax_i.axis("off")

    pdf.savefig(fig5, facecolor=DARK); plt.close(fig5)
    print("[DONE] Halaman 5 — Weibull + WPD")

    # ── Halaman 6: Wake Effect ────────────────────────────────────────────────
    print("[INFO] Membuat halaman 6 — Wake Effect...")
    fig6 = dark_fig()
    add_page_border(fig6, "Analisis Wake Effect — Layout Turbin", 6)

    for fname, pos in [("wake_layout_comparison.png",[0.04,0.50,0.92,0.40]),
                        ("aep_vs_spacing.png",        [0.04,0.08,0.92,0.38])]:
        fpath = os.path.join(cfg.DIR_OUTPUT, fname)
        ax_i = fig6.add_axes(pos)
        if os.path.exists(fpath):
            from PIL import Image
            img = np.array(Image.open(fpath))
            ax_i.imshow(img); ax_i.axis("off")
        else:
            ax_i.set_facecolor(NAVY); ax_i.axis("off")
            ax_i.text(0.5,0.5,fname,ha="center",va="center",color=GRAY,
                       fontsize=10,transform=ax_i.transAxes)

    # Tabel ringkasan AEP
    if wake_d and "layouts" in wake_d:
        ax_tbl = fig6.add_axes([0.04, 0.44, 0.92, 0.05])
        ax_tbl.axis("off"); ax_tbl.set_facecolor(DARK)
        lays = wake_d["layouts"]
        col_lbl = ["Layout", "AEP (GWh/yr)", "Wake Loss (%)", "Area (km²)", "Efisiensi (%)"]
        tbl_data = [[k, safe(v,"aep_gwh",default="—"), safe(v,"wake_loss_pct",default="—"),
                     safe(v,"farm_area_km2",default="—"), safe(v,"efficiency_pct",default="—")]
                    for k, v in lays.items()]
        tbl = ax_tbl.table(cellText=tbl_data, colLabels=col_lbl,
                            loc="center", cellLoc="center")
        tbl.auto_set_font_size(False); tbl.set_fontsize(9)
        for (r,c), cell in tbl.get_celld().items():
            cell.set_facecolor(NAVY if r>0 else CYAN+"33")
            cell.set_edgecolor(GRAY+"55")
            cell.set_text_props(color=GOLD if r==0 else LIGHT)

    pdf.savefig(fig6, facecolor=DARK); plt.close(fig6)
    print("[DONE] Halaman 6 — Wake Effect")

    # ── Halaman 7: Extreme Wind ───────────────────────────────────────────────
    print("[INFO] Membuat halaman 7 — Extreme Wind...")
    fig7 = dark_fig()
    add_page_border(fig7, f"Extreme Wind Analysis — IEC Class {iec_cls}", 7)

    for fname, pos in [("extreme_wind_return_period.png",[0.04,0.50,0.92,0.40]),
                        ("extreme_wind_seasonality.png", [0.04,0.08,0.92,0.38])]:
        fpath = os.path.join(cfg.DIR_OUTPUT, fname)
        ax_i = fig7.add_axes(pos)
        if os.path.exists(fpath):
            from PIL import Image
            img = np.array(Image.open(fpath))
            ax_i.imshow(img); ax_i.axis("off")
        else:
            ax_i.set_facecolor(NAVY); ax_i.axis("off")
            ax_i.text(0.5,0.5,fname,ha="center",va="center",color=GRAY,
                       fontsize=10,transform=ax_i.transAxes)

    # Return period table
    ax_rp_tbl = fig7.add_axes([0.04, 0.44, 0.92, 0.05])
    ax_rp_tbl.axis("off")
    rp_periods = [1, 5, 10, 25, 50, 100]
    rp_vals = [safe(extreme,"return_periods",str(T),"speed_ms",default="—") for T in rp_periods]
    vref_vals = [safe(extreme,"return_periods",str(T),"v_ref_ms",default="—") for T in rp_periods]
    tbl7 = ax_rp_tbl.table(
        cellText=[[str(T) for T in rp_periods], [str(v) for v in rp_vals],
                   [str(v) for v in vref_vals]],
        rowLabels=["Return Period (yr)", "Wind Speed (m/s)", "V_ref IEC (m/s)"],
        loc="center", cellLoc="center"
    )
    tbl7.auto_set_font_size(False); tbl7.set_fontsize(9)
    for (r,c), cell in tbl7.get_celld().items():
        cell.set_facecolor(NAVY if c>=0 else DARK)
        cell.set_edgecolor(GRAY+"44")
        cell.set_text_props(color=GOLD if r==0 else LIGHT)

    pdf.savefig(fig7, facecolor=DARK); plt.close(fig7)
    print("[DONE] Halaman 7 — Extreme Wind")

    # ── Halaman 8: Metodologi ─────────────────────────────────────────────────
    print("[INFO] Membuat halaman 8 — Metodologi...")
    fig8 = dark_fig()
    add_page_border(fig8, "Metodologi Analisis", 8)
    ax8 = fig8.add_axes([0.05, 0.08, 0.90, 0.80])
    ax8.axis("off"); ax8.set_facecolor(DARK)

    methodology_text = [
        ("1. Data Angin", "ERA5 ECMWF reanalysis 1980–2025, resolusi 0.125°, 1-jam.\n"
         "Variabel: u10, v10 (komponen zonal dan meridional 10m AGL)."),
        ("2. DEM", "DEMNAS Badan Informasi Geospasial (BIG) Indonesia, resolusi 8m.\n"
         "12 tile mencakup domain Tulungagung dan sekitarnya."),
        ("3. Ekstrapolasi Ketinggian", "Power Law: V(z) = V₁₀ × (z/10)^α\n"
         "α = 0.20 untuk onshore (kondisi netral, terrain terbuka)."),
        ("4. Downscaling Spasial", "Jackson-Hunt topographic speedup correction dari ERA5 ke grid 3km.\n"
         "speedup = 1 + (Δh/L) × f_shape × exposure_index.\n"
         "Roughness correction: ln(z/z₀_lokal) / ln(z/z₀_ERA5)."),
        ("5. Statistik Distribusi", "Weibull 2-parameter (Maximum Likelihood Estimation, scipy.stats).\n"
         "WPD = 0.5×ρ×λ³×Γ(1+3/k). Capacity Factor dari integrasi Weibull×power curve."),
        ("6. Wake Modeling", "Jensen/Park top-hat model.\n"
         "U_wake = U∞×(1 - (1-√(1-Ct))×(r₀/(r₀+kx))²). k = 0.05 (onshore)."),
        ("7. Extreme Wind", "Gumbel GEV fitted ke annual maxima (45 tahun).\n"
         "Return periods T=1,5,10,25,50,100 tahun. CI 90% via bootstrap N=500."),
        ("8. IEC Class", "V_ref = 1.4 × V₅₀. Class I: ≥50 m/s, II: ≥42.5, III: ≥37.5."),
        ("9. Keterbatasan", "Resolusi ERA5 0.125° tidak menangkap variabilitas sub-grid.\n"
         "Disarankan pengukuran anemometer 2 tahun minimum untuk validasi.\n"
         "CATATAN: Analisis ini TIDAK menggunakan WRF; downscaling murni statistik."),
    ]

    y_pos = 0.96
    for title, content in methodology_text:
        ax8.text(0.01, y_pos, f"▸ {title}", ha="left", va="top",
                  fontsize=10, color=CYAN, fontweight="bold")
        y_pos -= 0.04
        for line in content.split("\n"):
            ax8.text(0.04, y_pos, line, ha="left", va="top",
                      fontsize=9, color=LIGHT)
            y_pos -= 0.034
        y_pos -= 0.01

    pdf.savefig(fig8, facecolor=DARK); plt.close(fig8)
    print("[DONE] Halaman 8 — Metodologi")

    # ── Halaman 9: Referensi ──────────────────────────────────────────────────
    print("[INFO] Membuat halaman 9 — Referensi...")
    fig9 = dark_fig()
    add_page_border(fig9, "Referensi Ilmiah & Standar Teknis", 9)
    ax9 = fig9.add_axes([0.05, 0.08, 0.90, 0.80])
    ax9.axis("off"); ax9.set_facecolor(DARK)

    references = [
        ("[1] IEC 61400-1:2019", "Wind energy generation systems — Part 1: Design requirements. International Electrotechnical Commission."),
        ("[2] Hersbach et al. (2020)", "The ERA5 global reanalysis. Quarterly Journal of the Royal Meteorological Society, 146(730), 1999–2049."),
        ("[3] Jensen, N.O. (1983)", "A note on wind generator interaction. Risø National Laboratory, Roskilde, Denmark."),
        ("[4] Jackson & Hunt (1975)", "Turbulent wind flow over a low hill. Quarterly Journal of the Royal Meteorological Society, 101(430), 929–955."),
        ("[5] Gumbel, E.J. (1958)", "Statistics of Extremes. Columbia University Press."),
        ("[6] BIG Indonesia (2018)", "DEMNAS: Digital Elevation Model Nasional, resolusi 0.27 arcsec (~8m). Badan Informasi Geospasial."),
        ("[7] Manwell et al. (2009)", "Wind Energy Explained: Theory, Design and Application (2nd ed.). Wiley."),
        ("[8] Burton et al. (2011)", "Wind Energy Handbook (2nd ed.). Wiley-Blackwell."),
        ("[9] Vestas (2023)", "V150-4.5 MW™ — Technical Specifications. Vestas Wind Systems A/S."),
        ("[10] ESDM (2023)", "Rencana Umum Energi Nasional (RUEN) Update. Kementerian ESDM Indonesia."),
        ("[11] PLN (2023)", "RUPTL PLN 2023-2032. PT PLN (Persero)."),
        ("[12] Scipy (2020)", "SciPy 1.0: Fundamental Algorithms for Scientific Computing in Python. Nature Methods 17(3), 261–272."),
    ]

    y_pos = 0.96
    for ref, desc in references:
        ax9.text(0.01, y_pos, ref, ha="left", va="top",
                  fontsize=9.5, color=GOLD, fontweight="bold")
        ax9.text(0.22, y_pos, desc, ha="left", va="top",
                  fontsize=9, color=LIGHT, wrap=True)
        y_pos -= 0.075

    ax9.text(0.5, 0.02,
              "Laporan ini dibuat secara otomatis oleh pipeline Wind Resource Assessment Tulungagung.",
              ha="center", va="bottom", fontsize=8, color=GRAY, style="italic")

    pdf.savefig(fig9, facecolor=DARK); plt.close(fig9)
    print("[DONE] Halaman 9 — Referensi")

    d = pdf.infodict()
    d["Title"] = "Wind Resource Assessment Tulungagung — PLN"
    d["Subject"] = "PLTB Wind Farm Feasibility Study"
    d["Author"]  = "Wind Resource Assessment Pipeline (ERA5+DEMNAS)"
    d["Keywords"] = "PLTB, Tulungagung, ERA5, DEMNAS, Wind Resource, PLN"

files_ok.append(out_pdf)
print(f"\n[DONE] Modul 8 — PDF tersimpan: {out_pdf}")
print(f"         Ukuran: {os.path.getsize(out_pdf)/1024:.1f} KB")

elapsed = time.time() - t0
print("=" * 60)
print(f"  [DONE] Modul 8 selesai dalam {elapsed:.1f}s")
print(f"  Output: {out_pdf}")
print("=" * 60)
