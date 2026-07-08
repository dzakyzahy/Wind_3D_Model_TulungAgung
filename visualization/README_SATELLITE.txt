CARA MENYIAPKAN TEKSTUR SATELIT UNTUK VISUALISASI 3D:

1. Buka Google Maps atau Google Earth di browser/komputer Anda.
2. Set tampilan/view ke mode "Satellite" (Satelit) tanpa label/peta jalan jika memungkinkan.
3. Posisikan peta agar seluruh domain Tulungagung terlihat jelas dalam batas bounding box berikut:
   - Latitude: -9.29 hingga -7.29
   - Longitude: 110.8 hingga 112.8
4. Ambil tangkapan layar (screenshot) dengan orientasi landscape (horizontal).
5. Potong (crop) gambar menjadi bujur sangkar (persegi 1:1) agar pas dengan rasio aspek domain topografi 3D.
6. Simpan file gambar tersebut dengan nama tepat:
   satellite_texture.jpg
7. Letakkan file tersebut di dalam folder yang sama dengan file index.html, yaitu di:
   d:\ITB2\Pak_RK\MetOcean_Tulungagung\kode_zahy\WindModel3DProject\visualization\satellite_texture.jpg
8. Buka atau refresh file index.html di browser Anda, lalu centang kotak "Tekstur Satelit" pada panel kontrol di sebelah kanan atas.

Tips Tambahan:
- Untuk kualitas visual terbaik dan resolusi tinggi, sangat disarankan menggunakan Google Earth Pro (gratis di desktop) dan gunakan fitur "Save Image" dengan resolusi 4K (3840x2160) atau maksimal, lalu crop menjadi rasio 1:1.
- Jika file satellite_texture.jpg tidak ditemukan saat visualisasi dijalankan, sistem akan otomatis menggunakan pewarnaan elevasi standar (vertex colors) tanpa menyebabkan error.
