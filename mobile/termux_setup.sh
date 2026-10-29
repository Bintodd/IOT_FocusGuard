#!/data/data/com.termux/files/usr/bin/bash
# ==============================================================================
# FocusGuard - Skrip Otomasi Persiapan Lingkungan Termux Android
# Dijalankan langsung di Termux pada HP A maupun HP B
# ==============================================================================

echo "========================================================"
echo "      FocusGuard — Skrip Setup Termux Android"
echo "========================================================"

# 1. Update paket Termux
echo "[1/4] Memperbarui repositori paket Termux..."
pkg update -y && pkg upgrade -y

# 2. Install Python dan Termux:API
echo "[2/4] Menginstall Python, Git, dan Termux:API..."
pkg install -y python git termux-api

# 3. Install Library Python Paho-MQTT
echo "[3/4] Menginstall library Python paho-mqtt..."
pip install paho-mqtt

# 4. Verifikasi Termux Sensor
echo "[4/4] Memverifikasi akses sensor HP..."
if command -v termux-sensor &> /dev/null; then
    echo "[+] Perintah 'termux-sensor' terdeteksi."
    echo "[*] Mencoba membaca daftar sensor perangkat..."
    termux-sensor -l | head -n 30
    echo ""
    echo "[+] Lingkungan Termux siap digunakan untuk FocusGuard!"
else
    echo "[!] PERINGATAN: 'termux-sensor' belum dapat dijalankan."
    echo "    Pastikan aplikasi pendukung 'Termux:API' sudah diinstall dari F-Droid"
    echo "    dan izin sensor sudah diberikan di Pengaturan Android -> Aplikasi -> Termux:API."
fi

echo "========================================================"
