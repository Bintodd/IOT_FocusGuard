"""
FocusGuard Session Manager Module
Mengatur state machine sesi belajar, penyelarasan data timestamp,
fusi sensor berbasis aturan, penggabungan interval interupsi,
dan kalkulasi metrik kontinuitas (T_S, T_I, C, R_I).
"""

import time
import uuid
import logging
import threading
from typing import Dict, Any, List, Optional
from core.processor import SignalProcessor
from core.storage import SessionStorage

logger = logging.getLogger("FocusGuard.SessionManager")


class SessionManager:
    """
    Manajer sesi belajar FocusGuard.
    Thread-safe untuk menangani pembaruan data MQTT dan permintaan Web API secara simultan.
    """

    def __init__(
        self,
        storage: SessionStorage,
        hp_a_acc_th: float = 0.85,
        hp_a_gyro_th: float = 0.20,
        hp_b_acc_th: float = 1.30,
        hp_b_gyro_th: float = 0.35,
        min_interruption_sec: float = 1.5,
        merge_gap_sec: float = 4.0,
        heartbeat_timeout_sec: float = 5.0
    ):
        self.lock = threading.Lock()
        self.storage = storage

        # Thresholds
        self.hp_a_acc_th = hp_a_acc_th
        self.hp_a_gyro_th = hp_a_gyro_th
        self.hp_b_acc_th = hp_b_acc_th
        self.hp_b_gyro_th = hp_b_gyro_th
        self.min_interruption_sec = min_interruption_sec
        self.merge_gap_sec = merge_gap_sec
        self.heartbeat_timeout_sec = heartbeat_timeout_sec

        # Processor untuk masing-masing HP
        self.proc_a = SignalProcessor("study_phone", hp_a_acc_th, hp_a_gyro_th)
        self.proc_b = SignalProcessor("activity_ref", hp_b_acc_th, hp_b_gyro_th)

        # Heartbeat & Status Koneksi Perangkat
        self.hp_a_last_seen: float = 0.0
        self.hp_b_last_seen: float = 0.0
        self.hp_a_seq: int = -1
        self.hp_b_seq: int = -1

        # State Sesi: "IDLE", "RUNNING", "PAUSED", "COMPLETED"
        self.state: str = "IDLE"
        self.session_id: Optional[str] = None
        self.session_title: str = "Sesi Belajar"
        self.session_start_time: float = 0.0
        self.session_end_time: float = 0.0
        self.total_paused_duration: float = 0.0
        self.last_pause_time: float = 0.0

        # Pelacakan Interupsi
        self.active_interruption: Optional[Dict[str, Any]] = None
        self.raw_candidate_interruption: Optional[Dict[str, Any]] = None
        self.finalized_interruptions: List[Dict[str, Any]] = []

        # Buffer data terkini untuk visualisasi grafik di dashboard (maksimal 60 data poin)
        self.chart_buffer_a: List[Dict[str, Any]] = []
        self.chart_buffer_b: List[Dict[str, Any]] = []
        self.max_chart_points: int = 60

        # Status Fusi Terkini
        self.current_fused_state: str = "FOKUS_BELAJAR"
        self.current_fused_description: str = "Kedua HP stabil di posisi belajar."

    # ==========================================================================
    # MANAJEMEN SESI (START, PAUSE, RESUME, STOP)
    # ==========================================================================

    def start_session(self, title: str = "Sesi Belajar") -> Dict[str, Any]:
        """Memulai sesi belajar baru."""
        with self.lock:
            now = time.time()
            self.state = "RUNNING"
            self.session_id = f"SES-{time.strftime('%Y%m%d-%H%M%S')}-{str(uuid.uuid4())[:4]}"
            self.session_title = title or "Sesi Belajar"
            self.session_start_time = now
            self.session_end_time = 0.0
            self.total_paused_duration = 0.0
            self.last_pause_time = 0.0
            self.active_interruption = None
            self.raw_candidate_interruption = None
            self.finalized_interruptions.clear()
            self.chart_buffer_a.clear()
            self.chart_buffer_b.clear()
            self.current_fused_state = "FOKUS_BELAJAR"
            self.current_fused_description = "Sesi belajar dimulai. Memantau posisi HP."

            logger.info(f"Sesi dimulai: {self.session_id} - '{self.session_title}'")
            return self.get_session_summary()

    def pause_session(self) -> Dict[str, Any]:
        """Menjeda sesi belajar sementara."""
        with self.lock:
            if self.state == "RUNNING":
                now = time.time()
                self.state = "PAUSED"
                self.last_pause_time = now
                # Jika ada interupsi aktif saat dijeda, tutup interupsi tersebut
                if self.active_interruption:
                    self._close_active_interruption(now)
                logger.info("Sesi belajar dijeda.")
            return self.get_session_summary()

    def resume_session(self) -> Dict[str, Any]:
        """Melanjutkan sesi belajar setelah jeda."""
        with self.lock:
            if self.state == "PAUSED":
                now = time.time()
                pause_delta = now - self.last_pause_time
                self.total_paused_duration += max(0.0, pause_delta)
                self.state = "RUNNING"
                logger.info("Sesi belajar dilanjutkan.")
            return self.get_session_summary()

    def stop_session(self) -> Dict[str, Any]:
        """Menghentikan sesi belajar dan menyimpan hasilnya ke database riwayat."""
        with self.lock:
            if self.state in ["RUNNING", "PAUSED"]:
                now = time.time()
                if self.state == "PAUSED":
                    pause_delta = now - self.last_pause_time
                    self.total_paused_duration += max(0.0, pause_delta)
                self.session_end_time = now
                if self.active_interruption:
                    self._close_active_interruption(now)

                self.state = "COMPLETED"
                summary = self.get_session_summary()
                # Simpan ke storage permanen
                self.storage.save_session(summary)
                logger.info(f"Sesi dihentikan & disimpan: {self.session_id}")
                return summary
            return self.get_session_summary()

    # ==========================================================================
    # PEMROSESAN TELEMETRI SENSOR DARI MQTT
    # ==========================================================================

    def ingest_study_phone(self, payload: Dict[str, Any]):
        """Menerima dan memproses paket data telemetri dari HP A (Study Phone)."""
        now = time.time()
        with self.lock:
            self.hp_a_last_seen = now
            self.hp_a_seq = payload.get("seq", self.hp_a_seq + 1)

            sensors = payload.get("sensors", {})
            acc = sensors.get("accelerometer", {})
            gyro = sensors.get("gyroscope", {})

            ts = payload.get("timestamp", now)
            result = self.proc_a.process_sample(
                timestamp=ts,
                acc_x=float(acc.get("x", 0.0)),
                acc_y=float(acc.get("y", 0.0)),
                acc_z=float(acc.get("z", 9.81)),
                gyro_x=float(gyro.get("x", 0.0)),
                gyro_y=float(gyro.get("y", 0.0)),
                gyro_z=float(gyro.get("z", 0.0))
            )

            # Simpan titik untuk chart dashboard
            self.chart_buffer_a.append({
                "time": time.strftime("%H:%M:%S", time.localtime(now)),
                "acc_mag": result["acc_mag"],
                "gyro_mag": result["gyro_mag"],
                "is_moving": result["is_moving"]
            })
            if len(self.chart_buffer_a) > self.max_chart_points:
                self.chart_buffer_a.pop(0)

            # Evaluasi fusi sensor jika sesi sedang aktif berjalan
            if self.state == "RUNNING":
                self._evaluate_sensor_fusion(now)

    def ingest_activity_ref(self, payload: Dict[str, Any]):
        """Menerima dan memproses paket data telemetri dari HP B (Activity Reference)."""
        now = time.time()
        with self.lock:
            self.hp_b_last_seen = now
            self.hp_b_seq = payload.get("seq", self.hp_b_seq + 1)

            sensors = payload.get("sensors", {})
            acc = sensors.get("accelerometer", {})
            gyro = sensors.get("gyroscope", {})

            ts = payload.get("timestamp", now)
            result = self.proc_b.process_sample(
                timestamp=ts,
                acc_x=float(acc.get("x", 0.0)),
                acc_y=float(acc.get("y", 0.0)),
                acc_z=float(acc.get("z", 9.81)),
                gyro_x=float(gyro.get("x", 0.0)),
                gyro_y=float(gyro.get("y", 0.0)),
                gyro_z=float(gyro.get("z", 0.0))
            )

            # Simpan titik untuk chart dashboard
            self.chart_buffer_b.append({
                "time": time.strftime("%H:%M:%S", time.localtime(now)),
                "acc_mag": result["acc_mag"],
                "gyro_mag": result["gyro_mag"],
                "is_moving": result["is_moving"]
            })
            if len(self.chart_buffer_b) > self.max_chart_points:
                self.chart_buffer_b.pop(0)

            # Evaluasi fusi sensor jika sesi sedang aktif berjalan
            if self.state == "RUNNING":
                self._evaluate_sensor_fusion(now)

    # ==========================================================================
    # SENSOR FUSION & ALGORITMA DETEKSI INTERUPSI
    # ==========================================================================

    def _evaluate_sensor_fusion(self, current_time: float):
        """
        Logika Fusi Sensor & Deteksi Interupsi:
        Menggabungkan bukti fisik dari HP A (meja) dan HP B (pengguna).
        
        Tabel Kasus Fusi:
        1. HP A diam  & HP B diam   -> FOKUS_BELAJAR (Normal)
        2. HP A gerak & HP B diam   -> HP_DIANGKAT (Pengguna mengambil HP meja saat duduk)
        3. HP A gerak & HP B gerak  -> PINDAH_MEMBAWA_HP (Pengguna berdiri membawa HP)
        4. HP A diam  & HP B gerak  -> PENGGUNA_BERPINDAH (HP ditinggal, pengguna berjalan pergi)
        """
        a_moving = self.proc_a.latest_result.get("is_moving", False)
        b_moving = self.proc_b.latest_result.get("is_moving", False)

        is_interruption_now = False
        interruption_type = ""
        description = ""

        if not a_moving and not b_moving:
            self.current_fused_state = "FOKUS_BELAJAR"
            self.current_fused_description = "Kondisi stabil. Sesi belajar berjalan kontinu."
        elif a_moving and not b_moving:
            is_interruption_now = True
            interruption_type = "HP_DIANGKAT_DIMEJA"
            description = "HP meja terangkat / digerakkan (pengguna tetap di tempat)."
            self.current_fused_state = "INTERUPSI_HP_MEJA"
            self.current_fused_description = description
        elif a_moving and b_moving:
            is_interruption_now = True
            interruption_type = "PINDAH_MEMBAWA_HP"
            description = "Pengguna berpindah tempat sambil membawa HP belajar."
            self.current_fused_state = "INTERUPSI_PINDAH_MEMBAWA_HP"
            self.current_fused_description = description
        elif not a_moving and b_moving:
            # HP A tetap di meja, pengguna bergerak (misal mondar-mandir atau meninggalkan meja)
            is_interruption_now = True
            interruption_type = "PENGGUNA_MENINGGALKAN_MEJA"
            description = "HP A di meja diam, namun pengguna terdeteksi bergerak/meninggalkan meja."
            self.current_fused_state = "INTERUPSI_PENGGUNA_AWAY"
            self.current_fused_description = description

        # ----------------------------------------------------------------------
        # Pengelolaan Interval Interupsi & Debounce Filter (Senggolan Singkat)
        # ----------------------------------------------------------------------
        if is_interruption_now:
            if self.active_interruption is None:
                # Cek kandidat debounce
                if self.raw_candidate_interruption is None:
                    # Mulai kandidat interupsi baru
                    self.raw_candidate_interruption = {
                        "start_time": current_time,
                        "type": interruption_type,
                        "description": description
                    }
                else:
                    # Sudah ada kandidat, cek apakah sudah melampaui durasi minimum (debounce filter)
                    duration = current_time - self.raw_candidate_interruption["start_time"]
                    if duration >= self.min_interruption_sec:
                        # Terkonfirmasi sebagai interupsi valid!
                        # Cek apakah dapat digabungkan dengan interupsi terakhir yang baru saja selesai (Interval Merging)
                        if self.finalized_interruptions:
                            last_event = self.finalized_interruptions[-1]
                            gap = self.raw_candidate_interruption["start_time"] - last_event["end_time"]
                            if gap <= self.merge_gap_sec:
                                # Merge ke event sebelumnya
                                self.active_interruption = self.finalized_interruptions.pop()
                                self.active_interruption["type"] += f" + {interruption_type}"
                                self.raw_candidate_interruption = None
                                return

                        # Buat interupsi aktif baru
                        self.active_interruption = {
                            "event_id": f"INT-{len(self.finalized_interruptions) + 1}",
                            "start_time": self.raw_candidate_interruption["start_time"],
                            "type": self.raw_candidate_interruption["type"],
                            "description": self.raw_candidate_interruption["description"],
                            "start_str": time.strftime("%H:%M:%S", time.localtime(self.raw_candidate_interruption["start_time"]))
                        }
                        self.raw_candidate_interruption = None
            else:
                # Interupsi aktif sedang berlangsung, perbarui tipenya jika berubah
                if interruption_type not in self.active_interruption["type"]:
                    self.active_interruption["type"] += f" -> {interruption_type}"
        else:
            # Tidak terdeteksi interupsi pada frame ini
            self.raw_candidate_interruption = None
            if self.active_interruption is not None:
                # Selesaikan interupsi aktif
                self._close_active_interruption(current_time)

    def _close_active_interruption(self, end_time: float):
        """Menutup interval interupsi yang aktif dan menyimpannya ke daftar final."""
        if not self.active_interruption:
            return

        duration = round(end_time - self.active_interruption["start_time"], 1)
        if duration >= self.min_interruption_sec:
            event = {
                "event_id": self.active_interruption.get("event_id", f"INT-{len(self.finalized_interruptions)+1}"),
                "start_time": self.active_interruption["start_time"],
                "end_time": end_time,
                "duration_sec": duration,
                "start_str": self.active_interruption["start_str"],
                "end_str": time.strftime("%H:%M:%S", time.localtime(end_time)),
                "type": self.active_interruption["type"],
                "description": self.active_interruption["description"]
            }
            self.finalized_interruptions.append(event)
            logger.info(f"Interupsi selesai: {event['type']} selama {duration}s")

        self.active_interruption = None

    # ==========================================================================
    # KALKULASI METRIK KONTINUITAS (T_S, T_I, C, R_I)
    # ==========================================================================

    def calculate_metrics(self) -> Dict[str, Any]:
        """
        Menghitung metrik sesuai rumus formal FocusGuard:
        - T_S: Durasi sesi valid (detik)
        - T_I: Total durasi interupsi gabungan (detik)
        - C: Rasio kontinuitas sesi (%) = 100 * (1 - T_I / T_S)
        - R_I: Frekuensi interupsi per menit = N_I / (T_S / 60)
        """
        now = time.time()

        if self.state == "IDLE":
            return {
                "t_s_sec": 0.0,
                "t_i_sec": 0.0,
                "continuity_ratio": 100.0,
                "interruption_count": 0,
                "interruption_frequency": 0.0,
                "formatted_t_s": "00:00:00",
                "formatted_t_i": "00:00:00"
            }

        # Hitung T_S (Durasi sesi belajar valid tidak termasuk jeda/pause)
        if self.state in ["RUNNING", "PAUSED"]:
            ref_time = now if self.state == "RUNNING" else self.last_pause_time
            raw_duration = ref_time - self.session_start_time
        else: # COMPLETED
            raw_duration = self.session_end_time - self.session_start_time

        t_s = max(0.0, raw_duration - self.total_paused_duration)

        # Hitung T_I (Jumlah durasi seluruh interupsi yang telah digabung)
        t_i = sum(item["duration_sec"] for item in self.finalized_interruptions)

        # Tambahkan interupsi yang sedang aktif berjalan
        if self.active_interruption and self.state == "RUNNING":
            active_duration = max(0.0, now - self.active_interruption["start_time"])
            t_i += active_duration

        # Pastikan T_I tidak melebihi T_S
        t_i = min(t_i, t_s) if t_s > 0 else 0.0

        # Rasio Kontinuitas C = 100 * (1 - T_I / T_S)
        if t_s > 0:
            continuity = 100.0 * (1.0 - (t_i / t_s))
            continuity = max(0.0, min(100.0, continuity))
        else:
            continuity = 100.0

        # Jumlah interupsi berbeda N_I
        n_i = len(self.finalized_interruptions) + (1 if self.active_interruption else 0)

        # Frekuensi interupsi per menit R_I = N_I / (T_S / 60)
        t_s_minutes = t_s / 60.0
        r_i = (n_i / t_s_minutes) if t_s_minutes > 0.05 else 0.0

        return {
            "t_s_sec": round(t_s, 1),
            "t_i_sec": round(t_i, 1),
            "continuity_ratio": round(continuity, 1),
            "interruption_count": n_i,
            "interruption_frequency": round(r_i, 2),
            "formatted_t_s": self._format_seconds(t_s),
            "formatted_t_i": self._format_seconds(t_i)
        }

    @staticmethod
    def _format_seconds(seconds: float) -> str:
        s = int(seconds)
        h = s // 3600
        m = (s % 3600) // 60
        sec = s % 60
        return f"{h:02d}:{m:02d}:{sec:02d}"

    # ==========================================================================
    # STATUS & SUMMARY UNTUK DASHBOARD / API
    # ==========================================================================

    def get_session_summary(self) -> Dict[str, Any]:
        """Mengembalikan data komprehensif sesi untuk dashboard dan penyimpanan."""
        metrics = self.calculate_metrics()
        now = time.time()

        hp_a_online = (now - self.hp_a_last_seen) < self.heartbeat_timeout_sec if self.hp_a_last_seen > 0 else False
        hp_b_online = (now - self.hp_b_last_seen) < self.heartbeat_timeout_sec if self.hp_b_last_seen > 0 else False

        return {
            "session_id": self.session_id,
            "title": self.session_title,
            "state": self.state,
            "start_time_iso": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.session_start_time)) if self.session_start_time else None,
            "end_time_iso": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.session_end_time)) if self.session_end_time else None,
            "metrics": metrics,
            "current_fused_state": self.current_fused_state,
            "current_fused_description": self.current_fused_description,
            "devices": {
                "study_phone": {
                    "online": hp_a_online,
                    "last_seen_sec_ago": round(now - self.hp_a_last_seen, 1) if self.hp_a_last_seen > 0 else None,
                    "latest": self.proc_a.latest_result
                },
                "activity_ref": {
                    "online": hp_b_online,
                    "last_seen_sec_ago": round(now - self.hp_b_last_seen, 1) if self.hp_b_last_seen > 0 else None,
                    "latest": self.proc_b.latest_result
                }
            },
            "active_interruption": self.active_interruption,
            "interruptions": list(self.finalized_interruptions)
        }

    def get_dashboard_payload(self) -> Dict[str, Any]:
        """Menyajikan payload lengkap untuk antarmuka web dashboard."""
        with self.lock:
            summary = self.get_session_summary()
            summary["charts"] = {
                "study_phone": list(self.chart_buffer_a),
                "activity_ref": list(self.chart_buffer_b)
            }
            return summary
