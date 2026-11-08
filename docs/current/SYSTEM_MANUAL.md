# System Manual & Operations Guide — BARA (PKMM Karhutla)

> **Document Status:** IMPLEMENTED (Source of Truth)  
> **System Name:** BARA — Indonesia Fire Watch  
> **Source Directory:** `project_pkmm-master/`

---

## Technical Executive Summary (English)

BARA is an operational wildfire monitoring and early warning system for Indonesia. It connects two primary satellite remote sensing pipelines:
1. **Active Thermal Anomaly Detection (NASA FIRMS):** Fetches VIIRS S-NPP near-real-time thermal detections (375m) across Indonesia with in-memory caching and polygon filtering.
2. **Sentinel-2 L2A Multispectral Inference (Copernicus / AWS STAC):** Extracts surface reflectance across 6 bands and computes vegetation/moisture indices (NDVI, NDWI) to predict fire potential via a pretrained XGBoost model.
3. **Automated Bounded Monitoring:** Partitions user-defined bounding boxes into a $3 \times 3$ grid, runs sequential background sampling (max 5 points/cycle), persists state to `monitor_state.json`, and synthesizes response priorities.

---

## Petunjuk Operasional & Teknis (Bahasa Indonesia)

### 1. Menjalankan Aplikasi

Buka PowerShell di direktori `project_pkmm-master/`:

```powershell
cd project_pkmm-master
python -m pip install -r requirements.txt
python server.py
```

Buka `http://127.0.0.1:5000` di peramban web. Setelah dependensi terpasang, pengguna Windows juga dapat menjalankan `start.bat`.

### 2. Konfigurasi NASA FIRMS MAP_KEY

1. Minta MAP_KEY gratis di: https://firms.modaps.eosdis.nasa.gov/api/map_key/
2. Salin MAP_KEY yang dikirimkan melalui email.
3. Buat/sunting berkas `.env` di dalam folder `project_pkmm-master/`:
   ```ini
   FIRMS_MAP_KEY=YOUR_MAP_KEY_HERE
   NDWI_FORMULA=green_nir
   ```
4. Restart server Flask (`python server.py`).

**Catatan API:**
- Endpoint: `https://firms.modaps.eosdis.nasa.gov/api/area/csv/{MAP_KEY}/VIIRS_SNPP_NRT/94,-12,142,7/{1-3}`
- Data di-cache di memori selama 300 detik (5 menit) untuk menjaga kuota API.
- Koordinat disaring menggunakan batas poligon daratan `indonesia.geojson`.

### 3. Pemantauan Grid Otomatis

1. Klik tombol **Pilih area di peta (2 sudut)**.
2. Klik 2 sudut berlawanan pada peta (lebar dan tinggi antara $0.005^\circ$ hingga $2.0^\circ$, maksimal $\sim 220\text{ km}$).
3. Pilih interval: 30 menit, 1 jam, atau 3 jam.
4. Klik **Simpan area & mulai**.
5. Server membagi area menjadi grid $3 \times 3$ (maksimal 9 titik; titik laut diabaikan).
6. Worker memproses maksimal 5 titik per siklus secara bergiliran untuk menjaga penggunaan CPU/jaringan.
7. Status dan jadwal disimpan secara atomik pada `monitor_state.json`.

### 4. Urutan Prioritas Respons

- **Prioritas 1 (Indikasi Kebakaran Aktif):** Deteksi termal FIRMS dalam 24 jam terakhir. Diurutkan berdasarkan tanggal terbaru, keyakinan (`high` > `nominal`), FRP terbesar, lalu jam akuisisi.
- **Prioritas 2 (Potensi Kebakaran):** Titik grid hasil analisis Sentinel-2 dengan prediksi Kelas 1 (XGBoost) dan citra berumur $\le 14$ hari. Diurutkan berdasarkan probabilitas kelas 1.
  - *Deduplikasi:* Titik potensi dalam radius 1 km dari deteksi aktif ditekan untuk mencegah alarm ganda.
- **Hasil Historis (Kelas 1 - Citra Lama):** Hasil kelas 1 dengan citra berumur $> 14$ hari ditampilkan terpisah dan memerlukan analisis ulang dengan citra baru.

### 5. Pusat Notifikasi (Notification Center)

- Buka ikon lonceng pada header dashboard. Riwayat notifikasi disimpan di `notification_state.json` dan bertahan setelah server restart.
- Severity: **INFO** (operasional, data tidak tersedia), **WASPADA** (deteksi FIRMS berkualitas `h`/`n` dalam 24 jam atau Kelas 1 XGBoost dengan skor memadai), **DARURAT** (hanya lewat verifikasi petugas).
- Filter tersedia berdasarkan severity dan status baca. Status notifikasi (`UNREAD`, `READ`, `ACKNOWLEDGED`, `RESOLVED`, `DISMISSED`) terpisah dari status event. Notifikasi dapat dikembalikan ke `UNREAD`, dan event dapat diselesaikan lewat aksi **Selesaikan event** (mencatat petugas dan catatan penyelesaian).
- Deteksi termal dan prediksi model tetap **bukan konfirmasi kebakaran**. Kegagalan analisis selalu dicatat sebagai INFO, bukan status aman.
- Pengaturan opsional: `WASPADA_MIN_SCORE`, `NOTIFICATION_FIRMS_INTERVAL`, `NOTIFICATION_MAX_RECORDS`, `NOTIFICATION_MAX_EVENTS`, `VERIFY_TOKEN`. Nilai batas retensi `0` berarti tanpa batas.

### 6. Verifikasi & Pengujian

Jalankan rangkaian tes mandiri:
```powershell
python -m unittest test_app.py
python -m unittest test_monitoring.py
python -m unittest test_notifications.py
node test_frontend.cjs
```

