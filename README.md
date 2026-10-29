# FocusGuard — Sistem IoT Pemantau Kontinuitas Sesi Belajar & Deteksi Interupsi

FocusGuard adalah sistem IoT yang dirancang untuk memantau kontinuitas sesi belajar fisik secara objektif menggunakan fusi sensor gerak (accelerometer & gyroscope) pada dua ponsel Android dan satu laptop pemrosesan.

> 📖 **Panduan Langkah demi Langkah Lengkap:** Lihat file [`PANDUAN_PENGGUNAAN.md`](file:///C:/Users/ASUS/.gemini/antigravity/scratch/FocusGuard/PANDUAN_PENGGUNAAN.md) untuk instruksi mendalam instalasi Termux, izin sensor, dan operasional sesi.

---

## 1. Arsitektur Sistem

```
[ HP A: Study Phone ] (Di Meja Belajar)
  - Sensor: lsm6dsoq_acc, lsm6dsoq_gyro
  - Memantau pengangkatan / penggunaan HP di meja
       │
       ▼ (MQTT over TCP 1883 / TLS 8883)
[ HiveMQ Cloud / Public Broker ] 
       ▲
       │ (MQTT over TCP 1883 / TLS 8883)
[ HP B: Activity Reference ] (Di Saku Pengguna)
  - Sensor: ACCELEROMETER, GYROSCOPE
  - Memantau aktivitas fisik pengguna (duduk / berdiri / berjalan)
       │
       ▼
[ Laptop Hub & Dashboard ]
  - Receiver telemetri MQTT & sinkronisasi timestamp
  - Pemrosesan sinyal: Magnitudo, Baseline Gravity Tracking, Dynamic Deviation
  - Algoritma Fusi Sensor Berbasis Aturan (Rule-Based Sensor Fusion)
  - Penghitung Kontinuitas Sesi (T_S, T_I, C, R_I) & Log Interupsi
  - Real-time Web Dashboard (http://localhost:5000)
```

---

## 2. Struktur Proyek

```
FocusGuard/
├── config/
│   └── config.py               # Konfigurasi MQTT broker, topic, ambang batas (threshold)
├── core/
│   ├── __init__.py
│   ├── mqtt_client.py          # Klien MQTT laptop (subscriber telemetri & publisher event)
│   ├── processor.py            # Pemrosesan sinyal: magnitudo, EMA baseline, thresholding
│   ├── session_manager.py      # State machine sesi, interval merging, kalkulasi metrik (C, R_I)
│   └── storage.py              # Penyimpanan riwayat sesi ke session_history.json
├── mobile/
│   ├── hp_a_study_phone.py     # Script Termux HP A (lsm6dsoq_acc, lsm6dsoq_gyro)
│   ├── hp_b_activity_ref.py    # Script Termux HP B (ACCELEROMETER, GYROSCOPE)
│   ├── mock_devices.py         # IoT Mock Simulator untuk pengujian di laptop tanpa HP
│   └── termux_setup.sh         # Shell script bantu instalasi lingkungan Termux
├── web/
│   ├── static/
│   │   ├── css/style.css       # Styling & animasi dashboard
│   │   └── js/dashboard.js     # Real-time dashboard controller & Chart.js live rendering
│   ├── templates/
│   │   └── index.html          # Antarmuka web dashboard interaktif
│   └── server.py               # REST API & Web Server Flask
├── data/
│   └── session_history.json    # Database penyimpanan riwayat sesi belajar
├── main.py                     # Entrypoint server laptop
└── requirements.txt            # Dependensi Python
```

---

## 3. Instalasi Dependensi Laptop

Dependensi telah diinstall pada laptop. Jika perlu instalasi ulang:

```powershell
pip install -r requirements.txt
```

---

## 4. Panduan Menjalankan Sistem

### Langkah 1: Jalankan Server FocusGuard di Laptop

Buka terminal di folder FocusGuard dan jalankan:

```powershell
python main.py
```

Output terminal akan menampilkan:
- Status koneksi MQTT ke `broker.hivemq.com`
- Topik yang disubscribe
- Alamat Web Dashboard: `http://localhost:5000` (dan alamat IP LAN laptop)

Buka browser laptop dan akses `http://localhost:5000`.

---

### Langkah 2: Menyiapkan HP A & HP B di Aplikasi Termux

#### A. Persiapan Awal di Kedua HP Android:
1. Install aplikasi **Termux** (disarankan dari F-Droid).
2. Install aplikasi pendukung **Termux:API** dari F-Droid.
3. Buka **Pengaturan Android** -> **Aplikasi** -> **Termux:API** -> **Izin (Permissions)** -> Aktifkan izin **Sensor Fisik (Physical Activity / Body Sensors)**.
4. Buka Termux di HP dan jalankan perintah:
   ```bash
   pkg update -y && pkg install -y python termux-api
   pip install paho-mqtt
   ```
   *(Atau jalankan skrip bantu `bash termux_setup.sh`)*

---

#### B. Menjalankan HP A (Study Phone — Di Meja Belajar):
Salin file `mobile/hp_a_study_phone.py` ke HP A, lalu jalankan di Termux:

```bash
python hp_a_study_phone.py --project focusguard_group
```

*HP A akan langsung membaca sensor `lsm6dsoq_acc` dan `lsm6dsoq_gyro`, menampilkan monitor real-time, dan mengirimkan telemetri MQTT ke broker.*

---

#### C. Menjalankan HP B (Activity Reference — Di Saku Pengguna):
Salin file `mobile/hp_b_activity_ref.py` ke HP B, simpan di saku celana, lalu jalankan di Termux:

```bash
python hp_b_activity_ref.py --project focusguard_group
```

*HP B akan mendeteksi nama sensor secara dinamis (ACCELEROMETER dan GYROSCOPE), lalu mengirim telemetri ke broker.*

---

## 5. Pengujian Cepat Tanpa HP Fisik (Mock Simulator)

Jika ingin menguji seluruh alur kerja sistem, algoritma deteksi, fusi sensor, grafik Chart.js, dan metrik kontinuitas langsung di laptop:

1. Pastikan `python main.py` sedang berjalan di satu terminal.
2. Buka terminal baru di laptop dan jalankan:
   ```powershell
   python mobile/mock_devices.py --auto
   ```
3. Simulator akan otomatis menjalankan rangkaian uji:
   - Skenario 1: Belajar Tenang (Kedua HP Diam -> Kontinuitas 100%)
   - Skenario 2: Senggolan Meja Sesaat (Durasi 0.8s -> Terfilter oleh Debounce, False Positive Ditolak!)
   - Skenario 3: HP Meja Diangkat (HP A Bergerak, HP B Diam -> Interupsi Fisik Terdeteksi)
   - Skenario 4: Pengguna Meninggalkan Meja (HP A Diam, HP B Bergerak -> Interupsi Away Terdeteksi)
4. Amati pergerakan jarum/grafik dan log interupsi pada Dashboard Web di `http://localhost:5000`.

---

## 6. Formula Matematis & Logika Algoritma

### 1. Invariansi Rotasi Magnitudo Vektor
\[
a_{\mathrm{mag}}=\sqrt{a_x^2+a_y^2+a_z^2},\quad \omega_{\mathrm{mag}}=\sqrt{\omega_x^2+\omega_y^2+\omega_z^2}
\]
Besaran magnitudo skalar kebal terhadap perubahan orientasi HP (landscape, portrait, miring). Saat diam, $a_{\mathrm{mag}} \approx 9.81\ \text{m/s}^2$ dan $\omega_{\mathrm{mag}} \approx 0\ \text{rad/s}$.

### 2. Estimasi Baseline Gravitasi & Deviasi Dinamis
\[
g_{\mathrm{est}}(t) = \alpha \cdot a_{\mathrm{mag}}(t) + (1-\alpha) \cdot g_{\mathrm{est}}(t-1)
\]
\[
a_{\mathrm{dev}} = |a_{\mathrm{mag}} - g_{\mathrm{est}}|
\]

### 3. Matriks Fusi Sensor
| HP A (Meja) | HP B (Saku) | Klasifikasi Keadaan | Interpretasi Sistem |
| :--- | :--- | :--- | :--- |
| **Diam** | **Diam** | `FOKUS_BELAJAR` | Sesi belajar kontinu normal |
| **Bergerak** | **Diam** | `INTERUPSI_HP_MEJA` | HP di meja diangkat/digunakan sambil duduk |
| **Bergerak** | **Bergerak** | `INTERUPSI_PINDAH_MEMBAWA_HP` | Pengguna meninggalkan meja membawa HP |
| **Diam** | **Bergerak** | `INTERUPSI_PENGGUNA_AWAY` | Pengguna mondar-mandir / meninggalkan meja |

### 4. Debounce & Interval Merging
- **Debounce:** Gerakan dengan durasi $< 1.5$ detik (misal ketukan meja atau getaran sekilas) disaring sehingga tidak dihitung sebagai interupsi (mencegah false positive).
- **Interval Merging:** Jika interupsi berikutnya muncul dalam interval $\le 4.0$ detik setelah interupsi sebelumnya, kedua interval digabungkan menjadi satu kesatuan durasi untuk mencegah fragmentasi noise.

### 5. Metrik Kontinuitas Sesi
- **Rasio Kontinuitas:** $C = 100 \left(1 - \frac{T_I}{T_S}\right)$ (%)
- **Frekuensi Interupsi:** $R_I = \frac{N_I}{T_S / 60}$ (interupsi per menit)
