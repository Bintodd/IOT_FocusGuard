"""
FocusGuard Configuration Module
Menyimpan konfigurasi broker MQTT, topic, ambang batas (threshold) sensor,
serta parameter sistem pemrosesan data.
"""

import os

# ==============================================================================
# 1. KONFIGURASI MQTT BROKER
# ==============================================================================
# Default broker publik HiveMQ.
# Dapat diganti dengan cluster HiveMQ Cloud pribadi jika diperlukan.
BROKER_HOST = os.getenv("FOCUSGUARD_BROKER", "broker.hivemq.com")

# Port 1883 untuk koneksi standar TCP non-TLS (mudah diuji segera tanpa kendala sertifikat).
# Port 8883 untuk TLS terenkripsi sesuai rancangan arsitektur.
USE_TLS = os.getenv("FOCUSGUARD_USE_TLS", "false").lower() == "true"
BROKER_PORT = int(os.getenv("FOCUSGUARD_PORT", 8883 if USE_TLS else 1883))

# Kredensial opsional (jika menggunakan HiveMQ Cloud pribadi dengan autentikasi username/password)
MQTT_USERNAME = os.getenv("FOCUSGUARD_USER", None)
MQTT_PASSWORD = os.getenv("FOCUSGUARD_PASS", None)

# ID Proyek unik untuk namespace topic MQTT (menghindari tabrakan pesan dengan pengguna lain)
PROJECT_ID = os.getenv("FOCUSGUARD_PROJECT_ID", "focusguard_group")

# ==============================================================================
# 2. STRUKTUR TOPIC MQTT
# ==============================================================================
TOPIC_STUDY_PHONE = f"focusguard/{PROJECT_ID}/edge/study_phone/telemetry"
TOPIC_ACTIVITY_REF = f"focusguard/{PROJECT_ID}/edge/activity_reference/telemetry"
TOPIC_SESSION_CONTROL = f"focusguard/{PROJECT_ID}/session/control"
TOPIC_EVENTS = f"focusguard/{PROJECT_ID}/events"
TOPIC_SUMMARY = f"focusguard/{PROJECT_ID}/session/summary"

# ==============================================================================
# 3. IDENTITAS & NAMA SENSOR
# ==============================================================================
# HP A: Study Phone (di meja belajar)
# Sensor yang telah divalidasi pada Termux:API HP A
HP_A_ACC_SENSOR_NAME = "lsm6dsoq_acc"
HP_A_GYRO_SENSOR_NAME = "lsm6dsoq_gyro"

# HP B: Activity Reference (di saku pengguna)
# Sensor standar Android pada Termux:API
HP_B_ACC_SENSOR_NAME = "ACCELEROMETER"
HP_B_GYRO_SENSOR_NAME = "GYROSCOPE"

# ==============================================================================
# 4. AMBANG BATAS (THRESHOLD) & PARAMETER SIGNAL PROCESSING
# ==============================================================================
# Catatan Teknis:
# Magnitudo percepatan dalam keadaan diam di permukaan bumi adalah g ~ 9.81 m/s^2.
# Nilai threshold di bawah mengukur deviasi percepatan dinamis: |a_mag - g_baseline|.
# Gyroscope mengukur kecepatan sudut rotasi dalam rad/s (diam ~ 0 rad/s).

# HP A (Study Phone di Meja)
# Ambang batas mendeteksi HP diangkat/digunakan di atas meja
HP_A_ACC_DEV_THRESHOLD = 1.10      # m/s^2 (deviasi di atas gravitasi stabil)
HP_A_GYRO_MAG_THRESHOLD = 0.25     # rad/s (~14.3 deg/s)

# HP B (Activity Reference di Saku)
# Ambang batas mendeteksi pengguna berjalan/berpindah tempat
HP_B_ACC_DEV_THRESHOLD = 1.30      # m/s^2
HP_B_GYRO_MAG_THRESHOLD = 0.35     # rad/s

# Parameter Temporal
SAMPLING_INTERVAL_MS = 200         # ~5 Hz sampling rate dari HP (cukup hemat baterai & responsif)
HEARTBEAT_TIMEOUT_SEC = 5.0        # Jika HP tidak mengirim data > 5s -> Status Offline
MIN_INTERRUPTION_SEC = 1.5         # Interupsi minimum untuk menyaring senggolan meja sesaat (debounce)
MERGE_GAP_SEC = 4.0                # Gabungkan dua interupsi jika jedanya < 4 detik (interval merging)
USER_AWAY_CONFIRM_SEC = 4.0        # HP B bergerak terus menerus saat HP A diam -> User Away

# ==============================================================================
# 5. WEB DASHBOARD SERVER
# ==============================================================================
WEB_HOST = "0.0.0.0"
WEB_PORT = 5000
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
HISTORY_FILE = os.path.join(DATA_DIR, "session_history.json")
