# 🤖 MASTER PROMPT & HANDOVER CONTEXT — WIND MODEL 3D TULUNGAGUNG
**Versi: 5.0 (Complete Engineering Architecture, Gotchas & Future Roadmap Guide)**  
**Lokasi Proyek:** `d:\ITB2\Pak_RK\MetOcean_Tulungagung\kode_zahy\WindModel3DProject`

---

## 1. IDENTITAS & TUJUAN PROYEK
Kamu adalah **AI Coding Assistant & MetOcean/Wind Energy Specialist** kelas dunia. Kamu sedang melanjutkan pengembangan proyek **"Wind Resource Assessment & 3D Interactive Visualization — Tulungagung & Trenggalek, Jawa Timur"** (kerjasama kajian energi terbarukan PLN / ITB).

Proyek ini adalah sistem analisis meteorologi dan visualisasi teknik 3D interaktif berbasis **Three.js r168 (Vanilla JS + HTML5 + CSS3)** yang memodelkan potensi energi angin, relief topografi pegunungan daratan (DEMNAS 8m), batimetri samudra dalam (BATNAS hingga -3.663m), citra satelit resolusi tinggi (Sentinel-2 & Google Satellite), serta vektor GIS Rupa Bumi Indonesia (RBI 25K: Jalan Raya, Sungai, Batas Wilayah).

### 📍 Spesifikasi Domain Geografis & Grid:
*   **Bounding Box (WGS84 / EPSG:4326):**
    *   **Latitude:** `-9.29°` hingga `-7.29°` LS *(Selatan, mencakup daratan hingga samudra lepas Samudra Hindia).*
    *   **Longitude:** `110.80°` hingga `112.80°` BT *(Timur, mencakup Trenggalek, Tulungagung, Ponorogo timur, Blitar selatan).*
    *   **Dimensi Domain:** Lebar $2^\circ$ ($\sim 222\text{ km}$) $\times$ Tinggi $2^\circ$ ($\sim 222\text{ km}$).
*   **Titik Kajian Utama (PLN Site):** Niyama Beach, Tulungagung (`-8.292° LS, 111.797° BT`).
*   **Rentang Elevasi Nyata (Real Topography):** `-3.663 meter` (Palung Jawa/BATNAS) hingga `+3.068 meter` MSL (Puncak pegunungan utara/DEMNAS).
*   **Ketinggian Hub Angin (Hub Heights AGL):** `50m, 100m, dan 150m` (dengan referensi turbin Vestas V150-4.5MW IEC Class III).

---

## 2. ARSITEKTUR KODE & SISTEM BUNDLING (PENTING!)
Proyek ini dirancang agar **100% kompatibel dengan protokol `file://`** (bisa dibuka langsung dengan mendouble-klik `index.html` di browser tanpa perlu menjalankan local web server `npm run dev` atau `python -m http.server`).

### 📦 Strategi Anti-CORS (JS Bundling):
Browser modern memblokir `fetch()` atau `XMLHttpRequest` terhadap file lokal (`.json`, `.jpg`, `.tif`, `.geojson`) karena kebijakan CORS/Same-Origin. Untuk mengatasinya, seluruh data backend diproses oleh skrip Python dan dibungkus menjadi file `.js` yang menetapkan variabel global pada `window`:
1.  **`visualization/data_bundle.js`** $\rightarrow$ `window.WIND_DATA_BUNDLE` (Berisi topografi DEMNAS+BATNAS, angin ERA5, statistik Weibull, dan data wake shadow turbin). Dibuat oleh `processing/scripts/make_data_bundle.py`.
2.  **`visualization/sentinel2_bundle.js`** $\rightarrow$ `window.SENTINEL2_TEXTURE_BASE64` (Citra satelit Sentinel-2 resampled 2048x2048 dalam format Base64). Dibuat oleh `processing/scripts/process_sentinel2.py`.
3.  **`visualization/satellite_bundle.js`** $\rightarrow$ `window.SATELLITE_TEXTURE_BASE64` (Citra satelit Google Earth eksisting). Dibuat oleh `processing/scripts/make_satellite_bundle.py`.
4.  **`visualization/rbi_bundle.js`** $\rightarrow$ `window.RBI_DATA` (Vektor jalan raya, sungai, dan batas admin RBI).

### 🧩 Struktur Frontend Modular (`visualization/js/`):
*   **`config.js`**: Konstanta domain, skalar visual, koordinat label kota/gunung, parameter turbin Vestas V150-4.5MW, dan palet warna HSL/RGB.
*   **`physics.js`**: Logika fisika angin (Hukum Pangkat / Power Law, profil logaritmik, Turbulence Intensity TI, Jensen Wake Model loss, faktor kapasitas CF Weibull).
*   **`data_loader.js`**: Pemuatan data dari `window.WIND_DATA_BUNDLE`, validasi struktur, dan fallback data sintetis jika bundle gagal dimuat.
*   **`scene_helpers.js`**: Pembangun geometri Three.js (Terrain Mesh dengan vertex colors & texture mapping, Wireframe, permukaan laut MSL `0.0m`, overlay RBI, partikel angin 3D & ghost trails, WPD heatmap overlay, ekstrim wind zone, turbin, **Top-Down Validation Plane**, dan scalebar dinamis).
*   **`ui_controls.js`**: Event listener untuk antarmuka pengguna (panel kontrol yang bisa di-scroll/disembunyikan, dropdown pemilih tekstur satelit Google vs Sentinel-2, interaksi slider, tombol play/pause/reset, dan kamera).

---

## 3. KELEMAHAN & KESALAHAN YANG SERING TERJADI (*GOTCHAS & PITFALLS*)
⚠️ **BACA DAN PAHAMI BAGIAN INI SEBELUM MELAKUKAN EDIT KODE APA PUN!**

### 1. Kesenjangan Domain DEMNAS & "Gunung Hijau Bulat" (*Synthetic Fallback Bug*)
*   **Masalah**: Sebelumnya sempat terjadi bug di mana bentuk gunung di bagian utara/belakang terasa tidak pas dan muncul bentuk bukit bulat hijau sempurna seperti gunung buatan.
*   **Penyebab**: File DEMNAS yang didownload hanya mencakup sebagian kecil domain (`111.5°–112.5° BT` & `-8.5°–-7.75° LS`). Ketika skrip `01_mosaic_dem.py` dan `04_era5_dem_to_json.py` melakukan interpolasi ke seluruh domain proyek (`110.8°–112.8° BT` & `-9.29°–-7.29° LS`), area utara dan barat/timur yang kosong otomatis diisi menggunakan **rumus kurva lonceng Gaussian matematis (*synthetic fallback DEM*)** agar mesh tidak bolong.
*   **Solusi yang Sudah Diterapkan & Aturan Baru**: Kini folder `Data/Demnas/` telah dilengkapi dan dirapikan menjadi **59 tile DEMNAS 8m** yang menutupi seluruh domain. Saat menjalankan mosaik di `01_mosaic_dem.py`, **WAJIB** menggunakan parameter `bounds=(cfg.LON_MIN, cfg.LAT_MIN, cfg.LON_MAX, cfg.LAT_MAX)` pada fungsi `rasterio.merge.merge(src_files, bounds=...)`. Jangan pernah menghapus parameter `bounds` ini, atau mosaik akan memakan memori RAM berlebih dan koordinatnya bergeser!

### 2. Terbaliknya Koordinat UV pada Rotasi Plane Three.js
*   **Masalah**: Di Three.js, ketika Anda membuat `new THREE.PlaneGeometry(TS, TS)` dan memutarnya menjadi horizontal dengan `geo.rotateX(-Math.PI / 2)`, koordinat tekstur (UV) akan terbalik secara vertikal terhadap peta geografis bumi (utara menjadi selatan).
*   **Aturan Wajib**: Setiap kali membuat geometri bidang datar (seperti Terrain Mesh atau Validation Plane), Anda **WAJIB** melakukan pembalikan manual koordinat V pada buffer UV seperti berikut:
    ```javascript
    const posAttr = geo.attributes.position;
    const uvAttr = geo.attributes.uv;
    const uvArr = uvAttr.array;
    for (let i = 0; i < posAttr.count; i++) {
      const vx = posAttr.getX(i);
      const vz = posAttr.getZ(i);
      uvArr[i * 2]     = (vx / TS) + 0.5;         // U (Longitude barat-timur)
      uvArr[i * 2 + 1] = 1.0 - ((vz / TS) + 0.5); // V (Latitude utara-selatan dibalik!)
    }
    uvAttr.needsUpdate = true;
    ```

### 3. Batas Memori WebGL & Ukuran Tekstur Satelit (DecompressionBomb / Crash)
*   **Masalah**: File citra satelit asli seperti `sentinel2_texture_wgs84.tif` berukuran **1,15 GB** (496 juta piksel). Jika file sebesar ini dikonversi langsung ke Base64 atau dimuat ke WebGL TextureLoader, tab browser akan langsung *crash* (Out of Memory) atau Python mengalami error `DecompressionBombError`.
*   **Aturan Wajib**: Selalu gunakan resolusi maksimal **`2048 × 2048` piksel** (atau maksimal `3072 × 3072`) untuk tekstur yang dibundle ke browser. Pada skrip Python, gunakan `PIL.Image.MAX_IMAGE_PIXELS = None` dan lakukan *contrast stretching* (persentil 1% ke 99%) agar warna vegetasi hutan dan lautan terlihat tajam dan vibrant di browser.

### 4. Larangan Penggunaan `fetch()` untuk File Lokal
*   **Aturan Wajib**: Jangan pernah mencoba mengubah logika pemuatan data di `data_loader.js` atau `scene_helpers.js` menjadi menggunakan `fetch('wind_data.json')`. Tetap pertahankan arsitektur membaca dari `window.WIND_DATA_BUNDLE`, `window.SENTINEL2_TEXTURE_BASE64`, dan `window.SATELLITE_TEXTURE_BASE64` agar aplikasi bisa dibuka offline tanpa web server.

---

## 4. TUGAS & FITUR YANG AKAN DITAMBAHKAN KEDEPANNYA (*ROADMAP & CRITICAL NEXT TASKS*)
*(Catatan untuk AI Agent berikutnya: Bagian di bawah ini adalah RENCANA ROADMAP & INSTRUKSI IMPLEMENTASI untuk fitur-fitur masa depan. Jangan ubah kode eksisting sebelum memahami seluruh alur kerja berikut ini).*

### 🔥 1. [PRIORITAS UTAMA] Fitur Peta Heatmap Angin 2D Melayang & Ekspor ke Folder
USER meminta penambahan fitur baru yang sangat penting untuk validasi dan inspeksi kajian energi angin:
1.  **Top-Down 2D Wind/WPD Heatmap Validation Plane (Peta Heatmap Angin 2D Melayang)**:
    *   Buat fitur bidang datar 2D yang melayang tepat di atas puncak gunung tertinggi (serupa dengan mekanisme *Top-Down Validation Plane* untuk satelit yang sudah ada di `scene_helpers.js` pada fungsi `buildValidationPlane`).
    *   Bidang melayang baru ini khusus memetakan **Heatmap Kecepatan Angin (Wind Speed m/s) dan Wind Power Density (WPD W/m²)** secara 2D horizontal.
    *   **Tujuan**: Memudahkan engineer melakukan validasi visual, mencocokkan daerah konsentrasi energi angin tinggi (warna merah/keemasan) terhadap letak lembah dan punggungan bukit dari sudut pandang atas (*Top-Down View*) tanpa terhalang atau tertutup kontur vertikal lereng gunung 3D!
    *   **Kontrol UI**: Tambahkan tombol toggle *checkbox* **ON/OFF** di Control Panel (misalnya pada kelompok **"Elemen UI & GIS"** atau **"Layer Overlay"** dengan nama `🗺️ Heatmap Angin 2D Melayang (Top-Down Validation)`). Secara default atur dalam kondisi `OFF`.
    *   **Interaktivitas**: Ketika slider **Hub Height** (`50m, 100m, 150m AGL`) diubah oleh user, warna dan distribusi pada Peta Heatmap Angin 2D melayang ini harus otomatis ikut berubah mencerminkan kecepatan angin pada ketinggian baru tersebut!

2.  **Penyimpanan Hasil Heatmap 2D ke Dalam Folder (*Automated Heatmap Export*)**:
    *   Selain ditampilkan secara interaktif pada antarmuka 3D di browser, sistem backend Python (misal pada skrip baru atau di dalam `04_era5_dem_to_json.py`) harus **secara otomatis menggenerasi dan menyimpan gambar statis berkualitas tinggi (PNG / GeoTIFF / PDF)** dari peta heatmap angin 2D tersebut.
    *   **Struktur Folder Penyimpanan**: Simpan seluruh hasil keluaran gambar heatmap angin 2D secara rapi ke dalam folder:
        *   `processing/output/wind_heatmaps_2d/` (dan salin juga ke `visualization/heatmaps/` agar bisa diakses browser jika dibutuhkan).
    *   **Spesifikasi File Keluaran**:
        *   Buat peta terpisah untuk setiap level ketinggian: `heatmap_wspd_50m.png`, `heatmap_wspd_100m.png`, `heatmap_wspd_150m.png`, serta `heatmap_wpd_100m.png`.
        *   Sertakan elemen kartografi standar profesional: **Judul Kajian, Colorbar dengan satuan (m/s atau W/m²), Garis Kontur Topografi (interval 250m), Titik Lokasi Niyama Beach, dan Bounding Box Koordinat**.
        *   Gunakan colormap berstandar ilmiah (misal `cmocean.cm.speed`, `viridis`, atau palet kustom HSL kuning-merah-ungu) yang kontras terhadap latar belakang gelap.

---

### ✂️ 2. [ROADMAP FITUR BARU] Interaktif Domain Cropping & Dynamic Reprocessing
USER meminta rencana desain untuk fitur pemotongan wilayah kajian secara dinamis (*Interactive Bounding Box Cropping Tool*):
1.  **Antarmuka Peta Pemilih Batas Area Kajian (*Interactive 2D Cropping Map*)**:
    *   Tambahkan antarmuka peta 2D interaktif (misalnya menggunakan Leaflet.js, OpenLayers, atau mini-map kanvas 2D pada panel UI) yang menampilkan keseluruhan domain kajian Jawa Timur (`[110.8°–112.8° BT] × [-9.29°–-7.29° LS]`).
    *   Pada peta pemilih tersebut, sediakan fitur **kotak pemotong yang bisa diatur dan digeser bebas oleh user (*Draggable/Resizable Bounding Box Selection Tool*)** untuk memilih sub-domain atau area fokus tertentu (misalnya memotong khusus area pantai selatan Trenggalek, atau khusus kawasan pegunungan Gunung Wilis, atau hanya radius 15 km sekitar Niyama Beach).

2.  **Perhitungan Ulang & Rekonstruksi 3D Otomatis (*Dynamic Cropping & Reprocessing*)**:
    *   Ketika user menekan tombol **"Terapkan Crop & Rekonstruksi 3D (*Apply Crop & Rebuild*)"**, sistem akan memproses ulang data secara dinamis (baik melalui pemanggilan skrip backend Python atau pemrosesan array lokal di dalam memori JavaScript jika memungkinkan).
    *   **Cropping Raster**: Geometri topografi DEMNAS, batimetri BATNAS, serta tekstur satelit Sentinel-2 / Google akan dipotong (*clipped*) tepat sesuai kotak batas baru yang ditentukan user.
    *   **Kalkulasi Ulang Heatmap & Fisika Angin**: Seluruh **Heatmap Kecepatan Angin (m/s), Heatmap Wind Power Density (WPD W/m²), parameter Weibull (k & c), zona angin ekstrem, dan estimasi AEP akan DIHITUNG ULANG (*recalculated*)** berdasarkan luas, resolusi grid, dan topografi spesifik di dalam kotak pemotongan tersebut!
    *   **Fokus Visualisasi**: Model 3D kemudian dirender ulang agar secara eksklusif menampilkan relief topografi di dalam kotak pemotongan tersebut dengan resolusi grid yang jauh lebih rapat dan detail (*High-Definition Local Area Focus*).
    *   **Tujuan**: Memberikan fleksibilitas luar biasa kepada analis dan engineer PLN untuk beralih dengan mudah dari analisis regional skala luas (222 km × 222 km) ke analisis tapak skala mikro (misal 10 km × 10 km) dalam satu platform terintegrasi tanpa perlu mengedit file konfigurasi secara manual!

---

### 📋 3. Roadmap Pengembangan Lanjutan Lainnya:
*   **Modul Analisis Finansial & Bankability (LCOE & NPV Calculator)**: Menambahkan tab/panel kalkulator kelayakan ekonomi dinamis berdasarkan estimasi AEP (Annual Energy Production) dari turbin Vestas V150-4.5MW yang dipilih, menghitung CAPEX, OPEX, tarif listrik PLN, dan Payback Period.
*   **Simulasi Angin Musiman & Diurnal (*Time-Series Playback*)**: Menambahkan kontrol *slider waktu (Bulan 1–12 dan Jam 00–23)* pada antarmuka untuk memvisualisasikan dinamika perubahan arah dan kecepatan angin saat Monsun Barat (Angin Barat Daya) vs Monsun Timur (Angin Timur/Tenggara).
*   **Generator Laporan PDF Otomatis (*Bankable Report Generator*)**: Memperluas pipeline Python dengan pustaka `reportlab` untuk mengekspor dokumen laporan lengkap 30+ halaman berisi tabel Weibull, peta kontur WPD, analisis wake loss, dan rekomendasi tata letak turbin yang siap diserahkan kepada PLN dan investor.

---

## 5. PANDUAN EKSEKUSI & GAYA KOMUNIKASI
1.  **Prioritaskan Kualitas Visual (*Wow Factor*)**: Antarmuka harus selalu terlihat modern, elegan, menggunakan tema gelap (*dark mode*) bertema korporat engineering (PLN/ITB), dengan transisi halus dan micro-animation.
2.  **Jangan Merusak Fitur Eksisting**: Saat menambahkan fitur baru (seperti Heatmap Angin 2D Melayang atau Domain Cropping), pastikan fitur yang sudah ada seperti Peta Satelit Dual Layer (Sentinel-2 vs Google), Partikel Angin 3D, dan RBI Overlay tetap berfungsi sempurna tanpa konflik variabel di `state`.
3.  **Tulis Kode yang Bersih & Berdokumentasi**: Selalu gunakan sintaks yang jelas, pertahankan komentar penjelasan bahasa Indonesia/Inggris pada modul JS dan skrip Python.
4.  **Verifikasi Langsung**: Setelah melakukan edit pada skrip pemrosesan atau antarmuka web, lakukan pengujian log terminal atau verifikasi visual untuk memastikan tidak ada error pada console browser maupun backend!

---
*Selamat bekerja! Pertahankan standar kualitas rekayasa kelas dunia untuk mendukung transisi energi terbarukan Indonesia! 🌬️⚡🇮🇩*
