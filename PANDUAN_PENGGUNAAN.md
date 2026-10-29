# PANDUAN PENGGUNAAN SISTEM IoT FOCUSGUARD
## Dokumentasi Operasional Step-by-Step (End-to-End)

Dokumen ini berisi panduan langkah demi langkah cara menyiapkan, menjalankan, menguji, dan mengevaluasi prototipe IoT **FocusGuard**.

---

## DAFTAR ISI
1. [Prasyarat Perangkat & Lingkungan](#1-prasyarat-perangkat--lingkungan)
2. [Langkah 1: Menjalankan Server Utama di Laptop](#2-langkah-1-menjalankan-server-utama-di-laptop)
3. [Langkah 2: Menyiapkan Aplikasi Termux di Kedua HP Android](#3-langkah-2-menyiapkan-aplikasi-termux-di-kedua-hp-android)
4. [Langkah 3: Menjalankan HP A (Study Phone — Meja Belajar)](#4-langkah-3-menjalankan-hp-a-study-phone--meja-belajar)
5. [Langkah 4: Menjalankan HP B (Activity Reference — Saku Pengguna)](#5-langkah-4-menjalankan-hp-b-activity-reference--saku-pengguna)
6. [Langkah 5: Operasional Sesi Belajar di Web Dashboard](#6-langkah-5-operasional-sesi-belajar-di-web-dashboard)
7. [Langkah 6: Kalibrasi Threshold Sensor di Dashboard](#7-langkah-6-kalibrasi-threshold-sensor-di-dashboard)
8. [Langkah 7: Pengujian Cepat Tanpa HP (Mock Simulator)](#8-langkah-7-pengujian-cepat-tanpa-hp-mock-simulator)
9. [Troubleshooting & Solusi Kendala Teknis](#9-troubleshooting--solusi-kendala-teknis)

---

## 1. Prasyarat Perangkat & Lingkungan

Sebelum memulai, pastikan perangkat berikut telah tersedia:

| Perangkat | Peran / Posisi | Kebutuhan Software |
| :--- | :--- | :--- |
| **Laptop** | Pusat Pengolah & Web Dashboard | Python 3.10+ (dependensi: `flask`, `paho-mqtt`, `requests`, `numpy`) |
| **HP A (Study Phone)** | Diletakkan diam di meja belajar | Android, Termux (F-Droid), Termux:API (Sensor: `lsm6dsoq_acc`, `lsm6dsoq_gyro`) |
| **HP B (Activity Reference)** | Disimpan di saku celana pengguna | Android, Termux (F-Droid), Termux:API (Sensor: `ACCELEROMETER`, `GYROSCOPE`) |
| **Koneksi Internet** | Menghubungkan HP & Laptop | Terhubung ke internet untuk broker MQTT publik (`broker.hivemq.com`) |

---

## 2. Langkah 1: Menjalankan Server Utama di Laptop

Server laptop bertindak sebagai pusat fusi data, penghitung metrik kontinuitas, dan penyedia dashboard.

### 1.1 Buka Terminal Laptop (PowerShell / Command Prompt)
Arahkan ke folder proyek FocusGuard:
```powershell
cd C:\Users\ASUS\.gemini\antigravity\scratch\FocusGuard
```

### 1.2 Verifikasi Dependensi (Sudah Terpasang)
Jika ingin memastikan seluruh dependensi telah lengkap:
```powershell
pip install -r requirements.txt
```

### 1.3 Jalankan Server Utama
```powershell
python main.py
```

### 1.4 Hasil yang Diharapkan di Terminal Laptop:
```text
======================================================================
      FocusGuard — IoT Study Continuity & Interruption Monitor
======================================================================
[INFO] Storage riwayat sesi aktif: ...\data\session_history.json
[INFO] Menghubungkan ke broker MQTT di broker.hivemq.com:1883...
[INFO] Berhasil terhubung ke broker MQTT: broker.hivemq.com:1883
[INFO] Subscribed ke topik: focusguard/focusguard_group/edge/study_phone/telemetry
[INFO] Subscribed ke topik: focusguard/focusguard_group/edge/activity_reference/telemetry
[INFO] Subscribed ke topik: focusguard/focusguard_group/session/control

----------------------------------------------------------------------
  [+] MQTT Broker   : broker.hivemq.com:1883 (TLS: False)
  [+] Project ID    : focusguard_group
  [+] Web Dashboard : http://localhost:5000
  [+] Akses LAN     : http://192.168.x.x:5000
----------------------------------------------------------------------
```

### 1.5 Buka Dashboard
Buka browser favorit Anda (Chrome, Edge, Firefox) dan akses:
👉 **`http://localhost:5000`**

---

## 3. Langkah 2: Menyiapkan Aplikasi Termux di Kedua HP Android

Lakukan langkah ini pada **HP A** dan **HP B** (cukup dilakukan sekali).

### 3.1 Install Termux & Termux:API dari F-Droid
> [!IMPORTANT]
> **PENTING:** Jangan menginstall Termux dari Google Play Store karena versi Play Store sudah dihentikan perawatannya (*deprecated*) dan tidak dapat mengakses sensor dengan baik.

1. Download dan pasang **Termux** dari F-Droid:  
   🔗 https://f-droid.org/packages/com.termux/
2. Download dan pasang **Termux:API** dari F-Droid:  
   🔗 https://f-droid.org/packages/com.termux.api/

### 3.2 Berikan Izin Sensor Fisik pada Termux:API di Android
1. Buka menu **Pengaturan Android (Settings)** di HP Anda.
2. Pilih **Aplikasi (Apps)** -> cari dan buka **Termux:API**.
3. Pilih **Izin (Permissions)**.
4. Pastikan izin **Sensor Fisik / Aktivitas Fisik (Physical Activity / Body Sensors)** berada dalam posisi **Diizinkan (Allowed)**.

### 3.3 Siapkan Paket di Dalam Terminal Termux
Buka aplikasi **Termux**, lalu ketikkan perintah berikut:
```bash
pkg update -y && pkg upgrade -y
pkg install -y python git termux-api
pip install paho-mqtt
```

### 3.4 Uji Akses Sensor di Termux
Jalankan perintah ini untuk memastikan Termux dapat membaca sensor HP:
```bash
termux-sensor -l
```
Jika muncul daftar sensor perangkat dalam format JSON, Termux:API sudah siap digunakan!

---

## 4. Langkah 3: Menjalankan HP A (Study Phone — Meja Belajar)

HP A bertugas mengamati pergerakan pada meja belajar (sensor: `lsm6dsoq_acc` dan `lsm6dsoq_gyro`).

### 4.1 Transfer / Buat Skrip `hp_a_study_phone.py` di HP A
Ada beberapa cara mudah memindahkan file skrip ke HP A:

**Cara A: Download langsung via Curl di Termux HP A (Paling Mudah):**
Jika laptop dan HP dalam satu jaringan atau file dihosting, Anda bisa menyalinnya. Atau buat file langsung di Termux HP A:
```bash
curl -O https://raw.githubusercontent.com/<repo-anda>/mobile/hp_a_study_phone.py
```
*Atau* salin isi file `mobile/hp_a_study_phone.py` ke HP A menggunakan nano / editor teks:
```bash
nano hp_a_study_phone.py
# (Tempel isi file, lalu simpan dengan Ctrl+O -> Enter -> Ctrl+X)
```

### 4.2 Jalankan Skrip di HP A
Letakkan HP A di atas meja belajar dengan stabil, lalu jalankan:
```bash
python hp_a_study_phone.py --project focusguard_group
```

### 4.3 Output yang Diharapkan di HP A:
```text
=================================================================
  FocusGuard — HP A (Study Phone Agent)
  Target Meja Belajar | Sensor: lsm6dsoq_acc, lsm6dsoq_gyro
  Broker: broker.hivemq.com:1883 | Topic: focusguard/focusguard_group/edge/study_phone/telemetry
=================================================================
[+] MQTT Terhubung Berhasil.
[*] Memulai streaming sensor via: termux-sensor -s lsm6dsoq_acc,lsm6dsoq_gyro -d 200

[+] Memulai pengiriman telemetri. Tekan Ctrl+C untuk berhenti.
-----------------------------------------------------------------
[SEQ 00042] Acc:  9.81 m/s^2 | Gyro:  0.01 rad/s -> MQTT Sent
```

Di Web Dashboard laptop, kartu **HP A — Study Phone** akan langsung berubah status menjadi:
🟢 **ONLINE**

---

## 5. Langkah 4: Menjalankan HP B (Activity Reference — Saku Pengguna)

HP B bertugas merekam aktivitas gerak pengguna (duduk tenang vs berdiri/berjalan).

### 5.1 Transfer / Buat Skrip `hp_b_activity_ref.py` di HP B
Salin file `mobile/hp_b_activity_ref.py` ke HP B:
```bash
nano hp_b_activity_ref.py
# (Tempel isi file, lalu simpan dengan Ctrl+O -> Enter -> Ctrl+X)
```

### 5.2 Jalankan Skrip di HP B
Masukkan HP B ke saku celana Anda, lalu jalankan:
```bash
python hp_b_activity_ref.py --project focusguard_group
```

Skrip ini memiliki fitur **Sensor Auto-Discovery** yang otomatis mencocokkan nama sensor accelerometer dan gyroscope di HP B meskipun merk perangkat berbeda.

### 5.3 Output yang Diharapkan di HP B:
```text
=================================================================
  FocusGuard — HP B (Activity Reference Agent)
  Target Pengguna (Saku) | Referensi Aktivitas Gerak
=================================================================
[*] Sensor Terpilih: ACC='ACCELEROMETER', GYRO='GYROSCOPE'
[+] MQTT Terhubung Berhasil.
[*] Memulai streaming sensor via: termux-sensor -s ACCELEROMETER,GYROSCOPE -d 200

[+] Memulai pengiriman telemetri. Tekan Ctrl+C untuk berhenti.
-----------------------------------------------------------------
[SEQ 00038] Ref Acc:  9.82 m/s^2 | Ref Gyro:  0.02 rad/s -> MQTT Sent
```

Di Web Dashboard laptop, kartu **HP B — Activity Reference** akan langsung berubah status menjadi:
🟢 **ONLINE**

---

## 6. Langkah 5: Operasional Sesi Belajar di Web Dashboard

Buka **`http://localhost:5000`** di browser laptop Anda.

```
┌────────────────────────────────────────────────────────────────────────┐
│  FocusGuard IoT Prototype               Broker: broker.hivemq.com:1883 │
├────────────────────────────────────────────────────────────────────────┤
│  [STATUS FUSI BANNER] : FOKUS_BELAJAR                                  │
│  Kedua HP stabil di posisi baseline belajar normal.                    │
├────────────────────┬───────────────────┬───────────────┬───────────────┤
│ Rasio Kontinuitas  │ Durasi Sesi (T_S) │ Interupsi(T_I)│ Frekuensi(R_I)│
│      100.0%        │     00:15:20      │    00:00:00   │  0.00 /menit  │
├────────────────────┴───────────────────┴───────────────┴───────────────┤
│ [KONTROL SESI]  Judul: [ Belajar Modul 4 IoT     ] [Mulai] [Jeda] [Stop]│
├────────────────────────────────────────┬───────────────────────────────┤
│ HP A (Study Phone): ONLINE             │ HP B (Activity Ref): ONLINE   │
│ a_mag: 9.81 m/s²  w_mag: 0.01 rad/s    │ a_mag: 9.82 m/s²  w_mag: 0.02 │
│ Status: STATIONARY (DIAM)              │ Status: STATIONARY (DIAM)     │
├────────────────────────────────────────┴───────────────────────────────┤
│ [GRAFIK LIVE] Percepatan (a_mag) & Kecepatan Sudut Rotasi (w_mag)     │
├────────────────────────────────────────────────────────────────────────┤
│ [TABEL LOG INTERUPSI] ID | Mulai | Selesai | Durasi | Klasifikasi Fusi │
└────────────────────────────────────────────────────────────────────────┘
```

### Prosedur Penggunaan Sesi:
1. **Mulai Sesi:**
   - Masukkan judul sesi belajar pada input teks (contoh: *"Belajar Pemrosesan Sinyal"*).
   - Klik tombol **Mulai Sesi**.
   - Timer sesi ($T_S$) akan mulai berjalan menghitung waktu aktif belajar.

2. **Mengamati Kejadian Selama Belajar:**
   - **Kondisi Normal (Fokus):**
     HP A di meja diam, HP B di saku duduk tenang.  
     Status: `FOKUS_BELAJAR` (Banner Hijau).  
     Skor kontinuitas tetap `100.0%`.
   - **Uji Senggolan Meja Sesaat (< 1.5 detik):**
     Ketuk meja belajar secara singkat.  
     *Hasil:* Tidak tercatat sebagai interupsi karena disaring oleh algoritma **Debounce Filter** (menghindari *false-positive*).
   - **Interupsi HP Diangkat:**
     Angkat HP A dari meja untuk mengecek pesan atau media sosial (> 1.5 detik).  
     *Hasil:* Status langsung beralih ke `INTERUPSI_HP_MEJA` (Banner Oranye). Timer interupsi aktif berjalan, grafik gyro melonjak tajam.
   - **Pengguna Meninggalkan Meja:**
     Pengguna berdiri dan berjalan meninggalkan meja (HP A tetap di meja).  
     *Hasil:* HP B mendeteksi langkah gerak sementara HP A diam. Status beralih ke `INTERUPSI_PENGGUNA_AWAY`.

3. **Menjeda Sesi (Pause):**
   - Jika ingin beristirahat resmi (toilet/makan), tekan tombol **Jeda (Pause)**.
   - Timer berhenti menghitung dan waktu jeda **tidak** dihitung sebagai penalti interupsi.
   - Tekan **Lanjutkan (Resume)** saat kembali belajar.

4. **Mengakhiri Sesi (Stop & Simpan):**
   - Klik tombol **Selesai & Simpan**.
   - Sistem akan mengkalkulasi metrik final:
     $$C = 100 \left(1 - \frac{T_I}{T_S}\right), \quad R_I = \frac{N_I}{T_S / 60}$$
   - Ringkasan sesi otomatis disimpan ke file permanen `data/session_history.json`.
   - Buka tab **Riwayat Sesi Tersimpan** di dashboard untuk mengevaluasi riwayat sesi sebelumnya.

---

## 7. Langkah 6: Kalibrasi Threshold Sensor di Dashboard

Tiap meja belajar atau tipe sensor memiliki tingkat sensitivitas yang berbeda. Anda dapat menyesuaikan ambang batas (*threshold*) secara langsung tanpa perlu merestart program:

1. Klik tombol **Thresholds** di pojok kanan atas dashboard.
2. Jendela modal kalibrasi akan terbuka:
   - **HP A Ambang Deviasi Percepatan (m/s²):** Default `0.85`. Naikkan jika meja Anda sering terkena getaran ketikan keyboard.
   - **HP A Ambang Gyroscope (rad/s):** Default `0.20`. Nilai batas deteksi sudut saat HP diangkat dari posisi rebah.
   - **HP B Ambang Percepatan Saku (m/s²):** Default `1.30`. Batas deteksi langkah kaki pengguna saat berjalan.
   - **Durasi Debounce Minimum (detik):** Default `1.5`. Gerakan di bawah durasi ini dianggap senggolan tak sengaja.
   - **Jeda Penggabungan Interval (detik):** Default `4.0`. Menggabungkan interupsi bersambung agar tidak terhitung berkali-kali.
3. Klik **Simpan Perubahan**. Pengaturan langsung diterapkan seketika pada engine pemrosesan sinyal.

---

## 8. Langkah 7: Pengujian Cepat Tanpa HP (Mock Simulator)

Jika Anda ingin menguji sistem di kampus, lab, atau saat HP belum siap, gunakan **Mock Device Simulator** yang tersedia:

1. Pastikan server laptop aktif:
   ```powershell
   python main.py
   ```
2. Buka terminal kedua di laptop, lalu jalankan:
   ```powershell
   cd C:\Users\ASUS\.gemini\antigravity\scratch\FocusGuard
   python mobile/mock_devices.py --auto
   ```
3. Simulator akan menyimulasikan 5 skenario nyata secara otomatis:
   - **Skenario 1:** Belajar tenang selama 10 detik (HP A diam, HP B diam).
   - **Skenario 2:** Senggolan meja sesaat 0.8 detik (verifikasi debounce filter).
   - **Skenario 3:** HP di meja diangkat selama 7 detik (verifikasi deteksi interupsi fisik).
   - **Skenario 4:** Pengguna meninggalkan meja selama 6 detik (verifikasi sensor fusion HP B).
   - **Skenario 5:** Kembali belajar tenang.
4. Perhatikan bagaimana grafik Chart.js bergerak live di dashboard web dan tabel event mencatat interupsi secara otomatis.

---

## 9. Troubleshooting & Solusi Kendala Teknis

### Q1: `termux-sensor` di Termux tidak menghasilkan apa-apa atau error `command not found`?
**Solusi:**
1. Pastikan paket terpasang: `pkg install termux-api`.
2. Pastikan aplikasi pendukung **Termux:API** terinstall di Android (dari F-Droid, bukan Play Store).
3. Buka **Pengaturan HP -> Aplikasi -> Termux:API -> Izin -> Berikan Izin Sensor Tubuh/Fisik**.
4. Restart aplikasi Termux.

### Q2: Status HP di Web Dashboard tetap `OFFLINE`?
**Solusi:**
1. Pastikan HP dan laptop sama-sama memiliki koneksi internet aktif (karena broker `broker.hivemq.com` berbasis cloud).
2. Periksa apakah Project ID sama. Default proyek adalah `focusguard_group`. Jika Anda mengubahnya di laptop, pastikan menjalankan skrip di HP dengan flag:
   `python hp_a_study_phone.py --project <PROJECT_ID_ANDA>`

### Q3: Nama sensor HP A tidak terdeteksi (`lsm6dsoq_acc` tidak muncul)?
**Solusi:**
Jika perangkat HP A Anda ternyata memiliki penamaan sensor berbeda, periksa nama sensor di Termux dengan:
```bash
termux-sensor -l
```
Lalu jalankan skrip dengan menyebutkan nama sensor yang ada:
```bash
python hp_a_study_phone.py --acc-name <NAMA_ACC> --gyro-name <NAMA_GYRO>
```

### Q4: Port 5000 di laptop sudah digunakan aplikasi lain?
**Solusi:**
Buka file `config/config.py`, ubah baris:
```python
WEB_PORT = 5000  # Ubah menjadi misalnya 5050 atau 8080
```
Lalu restart `python main.py`.

---

**FocusGuard IoT Team — 2026**
