#!/usr/bin/env python3
"""
FocusGuard - Mock IoT Device Simulator
Menyimulasikan pengiriman telemetri dari HP A (Study Phone) dan HP B (Activity Reference)
langsung dari laptop ke broker MQTT HiveMQ.

Sangat bermanfaat untuk:
1. Memverifikasi seluruh alur sistem FocusGuard di laptop sebelum menguji HP fisik.
2. Menguji algoritma fusi sensor terhadap berbagai skenario:
   - Skenario 1: Belajar Tenang (Keduanya Diam -> Kontinuitas 100%)
   - Skenario 2: HP Meja Diangkat (HP A Gerak, HP B Diam -> Interupsi)
   - Skenario 3: Senggolan Meja Sesaat (< 1.5s -> Terfilter/Debounce)
   - Skenario 4: Pengguna Meninggalkan Meja (HP A Diam, HP B Gerak -> Interupsi Away)
   - Skenario 5: Berjalan Membawa HP (Keduanya Gerak -> Interupsi Pindah)
"""

import sys
import os
import json
import time
import math
import random
import argparse
import paho.mqtt.client as mqtt

# Tambahkan root path agar config dapat diakses jika dijalankan langsung
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.config import BROKER_HOST, BROKER_PORT, TOPIC_STUDY_PHONE, TOPIC_ACTIVITY_REF, PROJECT_ID


class MockDeviceSimulator:
    def __init__(self, broker=BROKER_HOST, port=BROKER_PORT, project_id=PROJECT_ID):
        self.broker = broker
        self.port = port
        self.project_id = project_id
        self.topic_a = f"focusguard/{self.project_id}/edge/study_phone/telemetry"
        self.topic_b = f"focusguard/{self.project_id}/edge/activity_reference/telemetry"

        try:
            self.client = mqtt.Client(
                mqtt.CallbackAPIVersion.VERSION2 if hasattr(mqtt, "CallbackAPIVersion") else None,
                client_id=f"focusguard_mock_{int(time.time())}"
            )
        except Exception:
            self.client = mqtt.Client(client_id=f"focusguard_mock_{int(time.time())}")

        self.seq_a = 0
        self.seq_b = 0
        self.running = False

    def connect(self):
        print(f"[*] Menghubungkan Mock Simulator ke {self.broker}:{self.port}...")
        self.client.connect(self.broker, self.port, keepalive=60)
        self.client.loop_start()
        print("[+] Mock Simulator Terhubung ke Broker MQTT.")

    def stop(self):
        self.running = False
        self.client.loop_stop()
        self.client.disconnect()
        print("\n[+] Mock Simulator Dihentikan.")

    def _generate_telemetry(self, device_id: str, seq: int, is_moving: bool) -> dict:
        """Menghasilkan data sensor accelerometer dan gyro realistis."""
        now = time.time()
        if not is_moving:
            # Kondisi Diam: gravitasi stabil ~9.81 m/s^2 dengan noise mikro
            acc_x = random.gauss(0.02, 0.03)
            acc_y = random.gauss(0.01, 0.03)
            acc_z = random.gauss(9.80, 0.04)

            gyro_x = random.gauss(0.0, 0.02)
            gyro_y = random.gauss(0.0, 0.02)
            gyro_z = random.gauss(0.0, 0.02)
        else:
            # Kondisi Bergerak: deviasi percepatan dinamis & rotasi tinggi
            phase = now * 4.0
            acc_x = random.gauss(1.2 * math.sin(phase), 0.25)
            acc_y = random.gauss(1.8 * math.cos(phase), 0.3)
            acc_z = random.gauss(9.8 + 2.0 * math.sin(phase * 0.7), 0.4)

            gyro_x = random.gauss(0.8 * math.sin(phase), 0.15)
            gyro_y = random.gauss(1.2 * math.cos(phase), 0.2)
            gyro_z = random.gauss(0.6 * math.sin(phase * 1.5), 0.15)

        sensor_name_acc = "lsm6dsoq_acc" if device_id == "study_phone" else "ACCELEROMETER"
        sensor_name_gyro = "lsm6dsoq_gyro" if device_id == "study_phone" else "GYROSCOPE"

        return {
            "device_id": device_id,
            "seq": seq,
            "timestamp": now,
            "sensors": {
                "accelerometer": {
                    "sensor_name": sensor_name_acc,
                    "x": round(acc_x, 4),
                    "y": round(acc_y, 4),
                    "z": round(acc_z, 4),
                    "unit": "m/s^2"
                },
                "gyroscope": {
                    "sensor_name": sensor_name_gyro,
                    "x": round(gyro_x, 4),
                    "y": round(gyro_y, 4),
                    "z": round(gyro_z, 4),
                    "unit": "rad/s"
                }
            }
        }

    def run_scenario(self, scenario_name: str, duration_sec: float, a_moving: bool, b_moving: bool):
        """Menjalankan satu skenario uji selama durasi tertentu."""
        print(f"\n>>> SKENARIO: {scenario_name} (Durasi: {duration_sec}s)")
        print(f"    HP A (Meja): {'BERGERAK' if a_moving else 'DIAM'} | HP B (Saku): {'BERGERAK' if b_moving else 'DIAM'}")

        end_time = time.time() + duration_sec
        interval = 0.2  # 5 Hz

        while time.time() < end_time and self.running:
            self.seq_a += 1
            self.seq_b += 1

            payload_a = self._generate_telemetry("study_phone", self.seq_a, a_moving)
            payload_b = self._generate_telemetry("activity_reference", self.seq_b, b_moving)

            self.client.publish(self.topic_a, json.dumps(payload_a), qos=0)
            self.client.publish(self.topic_b, json.dumps(payload_b), qos=0)

            time_left = round(end_time - time.time(), 1)
            sys.stdout.write(f"\r    Mengirim telemetri... Sisa waktu: {time_left:4.1f}s ")
            sys.stdout.flush()
            time.sleep(interval)
        print(" [Selesai]")

    def run_automated_suite(self):
        """Menjalankan rangkaian pengujian otomatis end-to-end FocusGuard."""
        self.running = True
        print("\n" + "=" * 65)
        print("  MEMULAI SUITE PENGUJIAN OTOMATIS FOCUSGUARD")
        print("=" * 65)

        try:
            # 1. Belajar Tenang (10 detik)
            self.run_scenario(
                scenario_name="1. Belajar Normal & Fokus (Kedua HP Diam)",
                duration_sec=10,
                a_moving=False,
                b_moving=False
            )

            # 2. Senggolan Meja Singkat (0.8 detik) - Harus terfilter debounce!
            self.run_scenario(
                scenario_name="2. Senggolan Meja Sesaat / Tap (< 1.5s -> Filter Debounce)",
                duration_sec=0.8,
                a_moving=True,
                b_moving=False
            )

            # Kembali tenang sebentar
            self.run_scenario(
                scenario_name="   Kembali Belajar Tenang",
                duration_sec=5,
                a_moving=False,
                b_moving=False
            )

            # 3. Interupsi HP Meja Diangkat (7 detik)
            self.run_scenario(
                scenario_name="3. Interupsi: HP Meja Diangkat / Digunakan (HP A Gerak, HP B Diam)",
                duration_sec=7,
                a_moving=True,
                b_moving=False
            )

            # Kembali tenang
            self.run_scenario(
                scenario_name="   Kembali Belajar Tenang",
                duration_sec=6,
                a_moving=False,
                b_moving=False
            )

            # 4. Pengguna Meninggalkan Meja (6 detik)
            self.run_scenario(
                scenario_name="4. Interupsi: Pengguna Beranjak / Mondar-Mandir (HP A Diam, HP B Gerak)",
                duration_sec=6,
                a_moving=False,
                b_moving=True
            )

            # Kembali tenang
            self.run_scenario(
                scenario_name="   Kembali Belajar Tenang",
                duration_sec=5,
                a_moving=False,
                b_moving=False
            )

            print("\n" + "=" * 65)
            print("  SUITE PENGUJIAN OTOMATIS SELESAI")
            print("  Buka Dashboard Web di http://localhost:5000 untuk melihat metrik.")
            print("=" * 65)

        except KeyboardInterrupt:
            print("\n[!] Pengujian dibatalkan oleh pengguna.")
        finally:
            self.stop()


def main():
    parser = argparse.ArgumentParser(description="FocusGuard Mock Device Telemetry Simulator")
    parser.add_argument("--auto", action="store_true", help="Jalankan rangkaian uji otomatis 40 detik")
    parser.add_argument("--mode", choices=["quiet", "study_moving", "user_away", "both_moving"], default=None,
                        help="Mode simulasi manual spesifik")
    args = parser.parse_args()

    simulator = MockDeviceSimulator()
    simulator.connect()

    if args.auto:
        simulator.run_automated_suite()
    elif args.mode:
        simulator.running = True
        a_mov = args.mode in ["study_moving", "both_moving"]
        b_mov = args.mode in ["user_away", "both_moving"]
        print(f"[*] Menjalankan mode manual: {args.mode}. Tekan Ctrl+C untuk berhenti.")
        try:
            while simulator.running:
                simulator.seq_a += 1
                simulator.seq_b += 1
                pa = simulator._generate_telemetry("study_phone", simulator.seq_a, a_mov)
                pb = simulator._generate_telemetry("activity_reference", simulator.seq_b, b_mov)
                simulator.client.publish(simulator.topic_a, json.dumps(pa), qos=0)
                simulator.client.publish(simulator.topic_b, json.dumps(pb), qos=0)
                sys.stdout.write(f"\r[Sent] Study={a_mov} Ref={b_mov} | Seq={simulator.seq_a}")
                sys.stdout.flush()
                time.sleep(0.2)
        except KeyboardInterrupt:
            simulator.stop()
    else:
        # Default menu interaktif
        simulator.run_automated_suite()


if __name__ == "__main__":
    main()
