"""
FocusGuard Signal Processing Module
Bertanggung jawab menghitung magnitudo sensor, estimasi baseline gravitasi,
penyaringan noise, dan ekstraksi fitur gerak berbasis aturan (rule-based).
"""

import math
from collections import deque
from typing import Dict, Any, Tuple, Optional


class SignalProcessor:
    """
    Pemroses sinyal sensor accelerometer dan gyroscope untuk satu perangkat.
    
    Prinsip Fisika & Alasan Pemilihan Fitur:
    1. Magnitudo Vektor Percepatan:
       a_mag = sqrt(a_x^2 + a_y^2 + a_z^2)
       Sifat: Invarian terhadap orientasi (rotational invariance).
       Tidak peduli HP diletakkan portrait, landscape, terlentang, atau miring,
       magnitudo percepatan dalam keadaan diam selalu bernilai gravitasi (~9.81 m/s^2).
       
    2. Magnitudo Kecepatan Sudut (Gyroscope):
       w_mag = sqrt(w_x^2 + w_y^2 + w_z^2)
       Mengukur total laju perubahan rotasi HP dalam ruang 3D (satuan rad/s).
       Dalam keadaan diam, w_mag mendekati 0 rad/s (hanya noise sensor kecil ~0.01-0.03 rad/s).
       Ketika HP diangkat atau disentuh, rotasi menghasilkan lonjakan w_mag yang sangat jelas.

    3. Estimasi Gravitasi Baseline (EMA):
       g_est(t) = alpha * a_mag(t) + (1 - alpha) * g_est(t-1)
       Digunakan untuk menghitung percepatan dinamis murni: a_dev = |a_mag - g_est|.
    """

    def __init__(
        self,
        device_id: str,
        acc_dev_threshold: float = 0.85,
        gyro_mag_threshold: float = 0.20,
        window_size: int = 10,
        ema_alpha: float = 0.05
    ):
        self.device_id = device_id
        self.acc_dev_threshold = acc_dev_threshold
        self.gyro_mag_threshold = gyro_mag_threshold
        self.window_size = window_size
        self.ema_alpha = ema_alpha

        # State tracking
        self.baseline_gravity: float = 9.81
        self.is_baseline_initialized: bool = False

        # Sliding window buffer untuk ekstraksi statistik
        self.acc_mag_history = deque(maxlen=window_size)
        self.gyro_mag_history = deque(maxlen=window_size)
        self.timestamps = deque(maxlen=window_size)

        # Hasil pemrosesan terakhir
        self.latest_result: Dict[str, Any] = {
            "device_id": self.device_id,
            "timestamp": 0.0,
            "acc_mag": 9.81,
            "acc_dev": 0.0,
            "gyro_mag": 0.0,
            "acc_std": 0.0,
            "gyro_std": 0.0,
            "is_moving": False,
            "trigger_reason": "none"
        }

    @staticmethod
    def calculate_magnitude(x: float, y: float, z: float) -> float:
        """Menghitung Euclidean norm dari vektor 3D."""
        return math.sqrt(x * x + y * y + z * z)

    def update_baseline(self, acc_mag: float, is_stationary_candidate: bool):
        """Memperbarui estimasi baseline gravitasi menggunakan Exponential Moving Average."""
        if not self.is_baseline_initialized:
            self.baseline_gravity = acc_mag
            self.is_baseline_initialized = True
            return

        # Hanya adaptasi baseline saat sinyal relatif tenang untuk mencegah baseline terdistorsi gerakan besar
        if is_stationary_candidate:
            self.baseline_gravity = (
                self.ema_alpha * acc_mag + (1.0 - self.ema_alpha) * self.baseline_gravity
            )

    @staticmethod
    def calculate_std(values: deque) -> float:
        """Menghitung standar deviasi dari sliding window."""
        n = len(values)
        if n < 2:
            return 0.0
        mean = sum(values) / n
        variance = sum((x - mean) ** 2 for x in values) / (n - 1)
        return math.sqrt(variance)

    def process_sample(
        self,
        timestamp: float,
        acc_x: float,
        acc_y: float,
        acc_z: float,
        gyro_x: float,
        gyro_y: float,
        gyro_z: float
    ) -> Dict[str, Any]:
        """
        Memproses satu frame data sensor dari accelerometer dan gyroscope.
        Mengembalikan metrik fitur dan status klasifikasi gerak perangkat.
        """
        # 1. Hitung Magnitudo Vektor
        acc_mag = self.calculate_magnitude(acc_x, acc_y, acc_z)
        gyro_mag = self.calculate_magnitude(gyro_x, gyro_y, gyro_z)

        # 2. Masukkan ke buffer geser
        self.acc_mag_history.append(acc_mag)
        self.gyro_mag_history.append(gyro_mag)
        self.timestamps.append(timestamp)

        # 3. Hitung variasi statistik (Standar Deviasi)
        acc_std = self.calculate_std(self.acc_mag_history)
        gyro_std = self.calculate_std(self.gyro_mag_history)

        # Inisialisasi awal baseline pada sampel pertama
        if not self.is_baseline_initialized:
            self.baseline_gravity = acc_mag
            self.is_baseline_initialized = True

        # 4. Deteksi Kondisi Tenang Fisik (Calm / Resting State)
        # HP di atas meja memiliki rotasi mendekati 0 rad/s dan deviasi percepatan sangat rendah (tanpa jitter)
        is_physically_calm = (gyro_mag < 0.12) and (acc_std < 0.15)

        if is_physically_calm:
            # Adaptasi baseline gravitasi secara kontinu terhadap nilai statis nyata HP di meja
            self.baseline_gravity = 0.15 * acc_mag + 0.85 * self.baseline_gravity

        # Deviasi percepatan terhadap baseline gravitasi yang terkalibrasi
        acc_dev = abs(acc_mag - self.baseline_gravity)

        # 5. Klasifikasi Gerakan Berbasis Fusi Multi-Fitur (Rule-Based Robust Thresholding)
        # Menghindari false positive akibat offset kalibrasi atau noise sensor statis:
        gyro_moving = (gyro_mag > self.gyro_mag_threshold) or (gyro_std > 0.15)
        acc_moving = (acc_dev > self.acc_dev_threshold) and (acc_std > 0.20)
        combined_moving = (acc_dev > 0.65 * self.acc_dev_threshold) and (gyro_mag > 0.65 * self.gyro_mag_threshold)

        # Jika sensor terbukti tenang, mutlak dinyatakan diam
        if is_physically_calm:
            is_moving = False
            trigger_reason = "none"
        else:
            is_moving = gyro_moving or acc_moving or combined_moving
            if gyro_moving and acc_moving:
                trigger_reason = "acc_and_gyro"
            elif gyro_moving:
                trigger_reason = "gyro_rotation"
            elif acc_moving:
                trigger_reason = "acc_dynamic"
            elif combined_moving:
                trigger_reason = "combined_motion"
            else:
                trigger_reason = "none"

        # Rekap hasil
        self.latest_result = {
            "device_id": self.device_id,
            "timestamp": timestamp,
            "acc_raw": {"x": acc_x, "y": acc_y, "z": acc_z},
            "gyro_raw": {"x": gyro_x, "y": gyro_y, "z": gyro_z},
            "acc_mag": round(acc_mag, 3),
            "acc_dev": round(acc_dev, 3),
            "gyro_mag": round(gyro_mag, 3),
            "acc_std": round(acc_std, 3),
            "gyro_std": round(gyro_std, 3),
            "baseline_gravity": round(self.baseline_gravity, 3),
            "is_moving": is_moving,
            "trigger_reason": trigger_reason
        }

        return self.latest_result
