#!/usr/bin/env python3
"""
FocusGuard - HP B (Activity Reference) Telemetry Publisher
Dijalankan di aplikasi Termux pada HP B (disimpan di saku pengguna).

Fungsi:
1. Membaca accelerometer dan gyroscope pengguna (referensi gerak tubuh/berjalan).
2. Mendeteksi nama sensor secara dinamis (ACCELEROMETER/GYROSCOPE standar atau custom).
3. Mengirimkan telemetri ke broker HiveMQ via topik:
   focusguard/<PROJECT_ID>/edge/activity_reference/telemetry
"""

import sys
import os
import json
import time
import argparse
import subprocess
import ssl
import paho.mqtt.client as mqtt

# Default konfigurasi
DEFAULT_BROKER = "broker.hivemq.com"
DEFAULT_PORT = 1883
DEFAULT_PROJECT_ID = "focusguard_group"
DEFAULT_DELAY_MS = 200  # ~5 Hz


def parse_args():
    parser = argparse.ArgumentParser(description="FocusGuard HP B (Activity Reference) Edge Agent")
    parser.add_argument("--broker", default=DEFAULT_BROKER, help="Alamat MQTT Broker")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Port MQTT Broker (1883 TCP / 8883 TLS)")
    parser.add_argument("--project", default=DEFAULT_PROJECT_ID, help="FocusGuard Project ID")
    parser.add_argument("--tls", action="store_true", help="Gunakan TLS (wajib port 8883)")
    parser.add_argument("--delay", type=int, default=DEFAULT_DELAY_MS, help="Interval delay sensor (ms)")
    parser.add_argument("--acc-name", default=None, help="Paksa nama sensor accelerometer (opsional)")
    parser.add_argument("--gyro-name", default=None, help="Paksa nama sensor gyroscope (opsional)")
    return parser.parse_args()


def check_termux_api():
    """Memeriksa ketersediaan perintah termux-sensor."""
    try:
        res = subprocess.run(["termux-sensor", "-h"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return res.returncode == 0 or "Usage" in res.stdout or "Usage" in res.stderr
    except FileNotFoundError:
        return False


def discover_sensors():
    """
    Mendeteksi nama sensor accelerometer dan gyroscope pada HP B secara otomatis.
    Sangat berguna karena nama sensor antar merk HP Android bisa berbeda.
    """
    acc_candidate = None
    gyro_candidate = None

    try:
        res = subprocess.run(["termux-sensor", "-l"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode == 0:
            data = json.loads(res.stdout)
            sensor_list = data.get("sensors", [])

            # Cari standar ACCELEROMETER dulu
            for s in sensor_list:
                s_upper = s.upper()
                if "ACCELEROMETER" in s_upper and not acc_candidate:
                    acc_candidate = s
                if "GYROSCOPE" in s_upper and not gyro_candidate:
                    gyro_candidate = s

            # Fallback jika belum ketemu
            if not acc_candidate:
                for s in sensor_list:
                    if "acc" in s.lower():
                        acc_candidate = s
                        break
            if not gyro_candidate:
                for s in sensor_list:
                    if "gyr" in s.lower():
                        gyro_candidate = s
                        break
    except Exception as e:
        print(f"[!] Warning saat sensor discovery: {e}")

    return acc_candidate or "ACCELEROMETER", gyro_candidate or "GYROSCOPE"


def main():
    args = parse_args()
    topic = f"focusguard/{args.project}/edge/activity_reference/telemetry"

    print("=" * 65)
    print("  FocusGuard — HP B (Activity Reference Agent)")
    print("  Target Pengguna (Saku) | Referensi Aktivitas Gerak")
    print("=" * 65)

    if not check_termux_api():
        print("[ERROR] Perintah 'termux-sensor' tidak ditemukan!")
        print("Silakan jalankan di Termux:")
        print("  pkg install termux-api")
        print("Dan pastikan aplikasi 'Termux:API' terinstall di Android & izin sensor diberikan.")
        sys.exit(1)

    # Deteksi nama sensor jika tidak dispesifikasikan manual
    acc_name = args.acc_name
    gyro_name = args.gyro_name
    if not acc_name or not gyro_name:
        discovered_acc, discovered_gyro = discover_sensors()
        acc_name = acc_name or discovered_acc
        gyro_name = gyro_name or discovered_gyro

    print(f"[*] Sensor Terpilih: ACC='{acc_name}', GYRO='{gyro_name}'")
    print(f"[*] Broker: {args.broker}:{args.port} | Topic: {topic}")

    # Inisialisasi MQTT
    try:
        client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2 if hasattr(mqtt, "CallbackAPIVersion") else None,
            client_id=f"hp_b_activity_{int(time.time())}"
        )
    except Exception:
        client = mqtt.Client(client_id=f"hp_b_activity_{int(time.time())}")

    if args.tls:
        print("[*] Mengaktifkan koneksi TLS (Port 8883)...")
        client.tls_set(cert_reqs=ssl.CERT_REQUIRED, tls_version=ssl.PROTOCOL_TLSv1_2)

    try:
        client.connect(args.broker, args.port, keepalive=60)
        client.loop_start()
        print("[+] MQTT Terhubung Berhasil.")
    except Exception as e:
        print(f"[!] Gagal terhubung ke MQTT: {e}")
        print("Pastikan koneksi internet HP B aktif.")
        sys.exit(1)

    sensor_target = f"{acc_name},{gyro_name}"
    cmd = ["termux-sensor", "-s", sensor_target, "-d", str(args.delay)]
    print(f"[*] Memulai streaming sensor via: {' '.join(cmd)}")

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
    except Exception as e:
        print(f"[ERROR] Gagal menjalankan termux-sensor: {e}")
        sys.exit(1)

    seq = 0
    buffer = ""
    latest_acc = {"x": 0.0, "y": 0.0, "z": 9.81}
    latest_gyro = {"x": 0.0, "y": 0.0, "z": 0.0}
    decoder = json.JSONDecoder()
    last_publish_time = 0.0

    print("\n[+] Memulai pengiriman telemetri. Tekan Ctrl+C untuk berhenti.")
    print("-" * 65)

    try:
        for line in iter(proc.stdout.readline, ''):
            if not line:
                break
            buffer += line

            while buffer:
                buffer = buffer.lstrip()
                if not buffer:
                    break
                try:
                    obj, idx = decoder.raw_decode(buffer)
                    buffer = buffer[idx:].lstrip()
                except json.JSONDecodeError:
                    break

                if acc_name in obj:
                    vals = obj[acc_name].get("values", [0.0, 0.0, 9.81])
                    if len(vals) >= 3:
                        latest_acc = {"x": round(vals[0], 4), "y": round(vals[1], 4), "z": round(vals[2], 4)}

                if gyro_name in obj:
                    vals = obj[gyro_name].get("values", [0.0, 0.0, 0.0])
                    if len(vals) >= 3:
                        latest_gyro = {"x": round(vals[0], 4), "y": round(vals[1], 4), "z": round(vals[2], 4)}

                # Throttle pengiriman telemetri agar sinkron (~5 Hz)
                now_t = time.time()
                if (now_t - last_publish_time) < (args.delay / 1000.0 * 0.8):
                    continue
                last_publish_time = now_t

                seq += 1
                payload = {
                    "device_id": "activity_reference",
                    "seq": seq,
                    "timestamp": time.time(),
                    "sensors": {
                        "accelerometer": {
                            "sensor_name": acc_name,
                            "x": latest_acc["x"],
                            "y": latest_acc["y"],
                            "z": latest_acc["z"],
                            "unit": "m/s^2"
                        },
                        "gyroscope": {
                            "sensor_name": gyro_name,
                            "x": latest_gyro["x"],
                            "y": latest_gyro["y"],
                            "z": latest_gyro["z"],
                            "unit": "rad/s"
                        }
                    }
                }

                payload_json = json.dumps(payload)
                client.publish(topic, payload_json, qos=0)

                acc_mag = (latest_acc["x"]**2 + latest_acc["y"]**2 + latest_acc["z"]**2)**0.5
                gyro_mag = (latest_gyro["x"]**2 + latest_gyro["y"]**2 + latest_gyro["z"]**2)**0.5
                sys.stdout.write(
                    f"\r[SEQ {seq:05d}] Ref Acc: {acc_mag:5.2f} m/s^2 | Ref Gyro: {gyro_mag:5.2f} rad/s -> MQTT Sent"
                )
                sys.stdout.flush()

    except KeyboardInterrupt:
        print("\n\n[*] Menghentikan pengiriman data...")
    finally:
        try:
            proc.terminate()
            subprocess.run(["termux-sensor", "-c"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass
        client.loop_stop()
        client.disconnect()
        print("[+] Selesai. HP B terputus secara bersih.")


if __name__ == "__main__":
    main()
