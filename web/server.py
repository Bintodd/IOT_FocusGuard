"""
FocusGuard Web Dashboard Server
Menyediakan antarmuka dashboard interaktif berbasis web (Flask)
untuk memantau status HP, timer sesi, metrik kontinuitas, grafik sensor,
dan log kejadian interupsi secara real-time.
"""

import os
import sys
import logging
from flask import Flask, render_template, jsonify, request
from core.session_manager import SessionManager
from core.storage import SessionStorage
from config.config import (
    BROKER_HOST, BROKER_PORT, USE_TLS, PROJECT_ID,
    TOPIC_STUDY_PHONE, TOPIC_ACTIVITY_REF,
    HP_A_ACC_DEV_THRESHOLD, HP_A_GYRO_MAG_THRESHOLD,
    HP_B_ACC_DEV_THRESHOLD, HP_B_GYRO_MAG_THRESHOLD,
    MIN_INTERRUPTION_SEC, MERGE_GAP_SEC
)

logger = logging.getLogger("FocusGuard.WebServer")


def create_app(session_manager: SessionManager, storage: SessionStorage) -> Flask:
    template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")
    static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

    app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)

    # Matikan log default Flask yang terlalu berisik saat polling
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.WARNING)

    @app.route("/")
    def index():
        """Halaman utama dashboard."""
        return render_template(
            "index.html",
            project_id=PROJECT_ID,
            broker_host=BROKER_HOST,
            broker_port=BROKER_PORT,
            use_tls=USE_TLS,
            topic_a=TOPIC_STUDY_PHONE,
            topic_b=TOPIC_ACTIVITY_REF
        )

    @app.route("/api/status", methods=["GET"])
    def get_status():
        """Mengembalikan data real-time sesi, sensor, dan status koneksi."""
        return jsonify(session_manager.get_dashboard_payload())

    @app.route("/api/session/start", methods=["POST"])
    def start_session():
        data = request.get_json(silent=True) or {}
        title = data.get("title", "Sesi Belajar Mandiri")
        res = session_manager.start_session(title=title)
        return jsonify({"success": True, "session": res})

    @app.route("/api/session/pause", methods=["POST"])
    def pause_session():
        res = session_manager.pause_session()
        return jsonify({"success": True, "session": res})

    @app.route("/api/session/resume", methods=["POST"])
    def resume_session():
        res = session_manager.resume_session()
        return jsonify({"success": True, "session": res})

    @app.route("/api/session/stop", methods=["POST"])
    def stop_session():
        res = session_manager.stop_session()
        return jsonify({"success": True, "session": res})

    @app.route("/api/history", methods=["GET"])
    def get_history():
        """Mengambil daftar seluruh riwayat sesi yang tersimpan."""
        sessions = storage.load_all_sessions()
        # Urutkan dari sesi terbaru
        sessions.reverse()
        return jsonify(sessions)

    @app.route("/api/history/clear", methods=["POST"])
    def clear_history():
        """Menghapus semua log riwayat sesi."""
        success = storage.clear_all_sessions()
        return jsonify({"success": success})

    @app.route("/api/config", methods=["GET", "POST"])
    def handle_config():
        """Membaca atau memperbarui ambang batas sensor secara dinamis."""
        if request.method == "POST":
            data = request.get_json(silent=True) or {}
            if "hp_a_acc_th" in data:
                session_manager.proc_a.acc_dev_threshold = float(data["hp_a_acc_th"])
            if "hp_a_gyro_th" in data:
                session_manager.proc_a.gyro_mag_threshold = float(data["hp_a_gyro_th"])
            if "hp_b_acc_th" in data:
                session_manager.proc_b.acc_dev_threshold = float(data["hp_b_acc_th"])
            if "hp_b_gyro_th" in data:
                session_manager.proc_b.gyro_mag_threshold = float(data["hp_b_gyro_th"])
            if "min_interruption_sec" in data:
                session_manager.min_interruption_sec = float(data["min_interruption_sec"])
            if "merge_gap_sec" in data:
                session_manager.merge_gap_sec = float(data["merge_gap_sec"])

            return jsonify({"success": True, "message": "Konfigurasi threshold diperbarui."})

        return jsonify({
            "hp_a_acc_th": session_manager.proc_a.acc_dev_threshold,
            "hp_a_gyro_th": session_manager.proc_a.gyro_mag_threshold,
            "hp_b_acc_th": session_manager.proc_b.acc_dev_threshold,
            "hp_b_gyro_th": session_manager.proc_b.gyro_mag_threshold,
            "min_interruption_sec": session_manager.min_interruption_sec,
            "merge_gap_sec": session_manager.merge_gap_sec,
            "broker": f"{BROKER_HOST}:{BROKER_PORT}",
            "project_id": PROJECT_ID
        })

    return app
