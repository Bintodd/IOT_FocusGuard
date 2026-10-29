"""
FocusGuard MQTT Client Module
Mengelola koneksi MQTT ke broker HiveMQ, langganan topik telemetri
HP A dan HP B, serta publikasi kejadian (events) dan ringkasan sesi.
"""

import json
import ssl
import time
import logging
from typing import Optional, Callable
import paho.mqtt.client as mqtt
from config.config import (
    BROKER_HOST, BROKER_PORT, USE_TLS, MQTT_USERNAME, MQTT_PASSWORD,
    TOPIC_STUDY_PHONE, TOPIC_ACTIVITY_REF, TOPIC_SESSION_CONTROL,
    TOPIC_EVENTS, TOPIC_SUMMARY
)
from core.session_manager import SessionManager

logger = logging.getLogger("FocusGuard.MQTT")


class FocusGuardMQTTClient:
    """Klien MQTT Laptop untuk menerima data sensor dan mengendalikan sesi."""

    def __init__(self, session_manager: SessionManager):
        self.session_manager = session_manager
        self.is_connected = False

        # Inisialisasi klien Paho MQTT (kompatibel Paho v1.x dan v2.x)
        try:
            self.client = mqtt.Client(
                mqtt.CallbackAPIVersion.VERSION2,
                client_id=f"focusguard_hub_{int(time.time())}"
            )
        except AttributeError:
            # Fallback untuk Paho MQTT v1.x
            self.client = mqtt.Client(client_id=f"focusguard_hub_{int(time.time())}")

        # Setup kredensial jika disediakan
        if MQTT_USERNAME and MQTT_PASSWORD:
            self.client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

        # Setup TLS jika diaktifkan (port 8883)
        if USE_TLS:
            logger.info("Mengaktifkan enkripsi TLS untuk koneksi MQTT.")
            self.client.tls_set(cert_reqs=ssl.CERT_REQUIRED, tls_version=ssl.PROTOCOL_TLSv1_2)

        # Pasang callback event
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        """Callback ketika terhubung ke broker."""
        rc_val = rc.value if hasattr(rc, "value") else rc
        if rc_val == 0:
            self.is_connected = True
            logger.info(f"Berhasil terhubung ke broker MQTT: {BROKER_HOST}:{BROKER_PORT}")

            # Langganan topik telemetri kedua HP & kontrol sesi
            client.subscribe([(TOPIC_STUDY_PHONE, 0), (TOPIC_ACTIVITY_REF, 0), (TOPIC_SESSION_CONTROL, 0)])
            logger.info(f"Subscribed ke topik: {TOPIC_STUDY_PHONE}")
            logger.info(f"Subscribed ke topik: {TOPIC_ACTIVITY_REF}")
            logger.info(f"Subscribed ke topik: {TOPIC_SESSION_CONTROL}")
        else:
            self.is_connected = False
            logger.error(f"Gagal terhubung ke broker MQTT. Return Code: {rc_val}")

    def _on_disconnect(self, client, userdata, flags_or_rc, *args):
        """Callback ketika koneksi terputus."""
        self.is_connected = False
        rc_val = getattr(flags_or_rc, "value", flags_or_rc)
        if rc_val != 0 and str(rc_val) != "Success":
            logger.warning(f"Koneksi ke broker MQTT terputus (code: {rc_val}). Menunggu reconnect...")

    def _on_message(self, client, userdata, msg):
        """Callback penanganan pesan masuk dari broker."""
        topic = msg.topic
        try:
            payload_str = msg.payload.decode("utf-8")
            data = json.loads(payload_str)
        except Exception as e:
            logger.warning(f"Gagal mendecode payload JSON dari {topic}: {e}")
            return

        try:
            if topic == TOPIC_STUDY_PHONE:
                self.session_manager.ingest_study_phone(data)
            elif topic == TOPIC_ACTIVITY_REF:
                self.session_manager.ingest_activity_ref(data)
            elif topic == TOPIC_SESSION_CONTROL:
                self._handle_session_control(data)
        except Exception as e:
            logger.error(f"Error memproses pesan dari {topic}: {e}", exc_info=True)

    def _handle_session_control(self, command_data: dict):
        """Menangani perintah kontrol sesi via MQTT."""
        cmd = command_data.get("command", "").lower()
        if cmd == "start":
            title = command_data.get("title", "Sesi Belajar (MQTT)")
            self.session_manager.start_session(title)
        elif cmd == "pause":
            self.session_manager.pause_session()
        elif cmd == "resume":
            self.session_manager.resume_session()
        elif cmd == "stop":
            summary = self.session_manager.stop_session()
            self.publish_summary(summary)

    def publish_event(self, event_data: dict):
        """Mempublikasikan kejadian interupsi ke topik events."""
        if self.is_connected:
            try:
                payload = json.dumps(event_data)
                self.client.publish(TOPIC_EVENTS, payload, qos=0)
            except Exception as e:
                logger.error(f"Gagal mempublikasikan event: {e}")

    def publish_summary(self, summary_data: dict):
        """Mempublikasikan ringkasan akhir sesi ke topik summary."""
        if self.is_connected:
            try:
                payload = json.dumps(summary_data)
                self.client.publish(TOPIC_SUMMARY, payload, qos=1)
            except Exception as e:
                logger.error(f"Gagal mempublikasikan summary sesi: {e}")

    def start(self):
        """Memulai loop MQTT di latar belakang (background thread)."""
        logger.info(f"Menghubungkan ke broker MQTT di {BROKER_HOST}:{BROKER_PORT}...")
        try:
            self.client.connect(BROKER_HOST, BROKER_PORT, keepalive=60)
            self.client.loop_start()
        except Exception as e:
            logger.error(f"Gagal inisialisasi koneksi MQTT: {e}")

    def stop(self):
        """Menghentikan loop MQTT."""
        try:
            self.client.loop_stop()
            self.client.disconnect()
            logger.info("Koneksi MQTT dihentikan.")
        except Exception as e:
            logger.error(f"Error saat menghentikan MQTT: {e}")
