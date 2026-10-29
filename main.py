#!/usr/bin/env python3
"""
FocusGuard - Main Processing Server & Web Dashboard Entrypoint
Titik masuk utama server laptop untuk menjalankan FocusGuard IoT Hub:
1. Menghubungkan MQTT Client ke HiveMQ Broker (subs telemetri HP A & HP B).
2. Menjalankan engine pemrosesan sinyal dan fusi sensor real-time.
3. Menyediakan Web Dashboard di http://localhost:5000.
"""

import sys
import os
import signal
import socket
import logging
from config.config import (
    BROKER_HOST, BROKER_PORT, USE_TLS, PROJECT_ID,
    WEB_HOST, WEB_PORT, HISTORY_FILE,
    HP_A_ACC_DEV_THRESHOLD, HP_A_GYRO_MAG_THRESHOLD,
    HP_B_ACC_DEV_THRESHOLD, HP_B_GYRO_MAG_THRESHOLD,
    MIN_INTERRUPTION_SEC, MERGE_GAP_SEC, HEARTBEAT_TIMEOUT_SEC
)
from core.storage import SessionStorage
from core.session_manager import SessionManager
from core.mqtt_client import FocusGuardMQTTClient
from web.server import create_app

# Konfigurasi Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (%(name)s) %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("FocusGuard.Main")


def get_local_ip() -> str:
    """Mendapatkan alamat IP lokal laptop pada jaringan WiFi."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def main():
    print("=" * 70)
    print("      FocusGuard — IoT Study Continuity & Interruption Monitor")
    print("=" * 70)

    # 1. Inisialisasi Storage
    storage = SessionStorage(HISTORY_FILE)
    logger.info(f"Storage riwayat sesi aktif: {HISTORY_FILE}")

    # 2. Inisialisasi Session Manager
    session_manager = SessionManager(
        storage=storage,
        hp_a_acc_th=HP_A_ACC_DEV_THRESHOLD,
        hp_a_gyro_th=HP_A_GYRO_MAG_THRESHOLD,
        hp_b_acc_th=HP_B_ACC_DEV_THRESHOLD,
        hp_b_gyro_th=HP_B_GYRO_MAG_THRESHOLD,
        min_interruption_sec=MIN_INTERRUPTION_SEC,
        merge_gap_sec=MERGE_GAP_SEC,
        heartbeat_timeout_sec=HEARTBEAT_TIMEOUT_SEC
    )

    # 3. Inisialisasi & Jalankan MQTT Client
    mqtt_client = FocusGuardMQTTClient(session_manager)
    mqtt_client.start()

    # 4. Buat Aplikasi Web Flask
    app = create_app(session_manager, storage)
    local_ip = get_local_ip()

    print("\n" + "-" * 70)
    print(f"  [+] MQTT Broker   : {BROKER_HOST}:{BROKER_PORT} (TLS: {USE_TLS})")
    print(f"  [+] Project ID    : {PROJECT_ID}")
    print(f"  [+] Web Dashboard : http://localhost:{WEB_PORT}")
    print(f"  [+] Akses LAN     : http://{local_ip}:{WEB_PORT}")
    print("-" * 70 + "\n")

    # Handler graceful shutdown
    def handle_exit(signum, frame):
        print("\n[*] Menutup FocusGuard Server...")
        mqtt_client.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)

    # Jalankan Web Server Flask
    try:
        app.run(host=WEB_HOST, port=WEB_PORT, debug=False, use_reloader=False)
    except Exception as e:
        logger.error(f"Server terhenti: {e}")
    finally:
        mqtt_client.stop()


if __name__ == "__main__":
    main()
