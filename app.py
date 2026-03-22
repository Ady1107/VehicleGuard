"""
VehicleGuard — Flask Backend (AWS)
Receives data from ESP32 via HTTP GET
Writes to Firebase Realtime Database

Install:
  pip install flask flask-cors requests
Run:
  python3 app.py
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime
import math, requests, json

app = Flask(__name__)
CORS(app)

# ── Firebase ──
FIREBASE_URL = "https://vehicleguard-847e6-default-rtdb.firebaseio.com"

# ── Thresholds ──
ACCIDENT_THRESHOLD = 1.2   # g-force — matches ESP32
FREEFALL_THRESHOLD = 0.2   # g-force

# ── Firebase helpers ──
def fb_put(path, data):
    try:
        r = requests.put(f"{FIREBASE_URL}/{path}.json",
                         data=json.dumps(data), timeout=5)
        return r.status_code == 200
    except Exception as e:
        print(f"[Firebase PUT error] {e}"); return False

def fb_post(path, data):
    try:
        r = requests.post(f"{FIREBASE_URL}/{path}.json",
                          data=json.dumps(data), timeout=5)
        return r.status_code == 200
    except Exception as e:
        print(f"[Firebase POST error] {e}"); return False

# ============================================================
# RECEIVE DATA FROM ESP32
# GET /api/data?lat=..&lon=..&ax=..&ay=..&az=..&gx=..&gy=..&gz=..
# ax/ay/az are in g-force (ESP32 divides by 16384)
# ============================================================
@app.route('/api/data', methods=['GET'])
def receive():
    try:
        lat = request.args.get("lat")
        lon = request.args.get("lon")
        ax  = float(request.args.get("ax", 0))
        ay  = float(request.args.get("ay", 0))
        az  = float(request.args.get("az", 0))
        gx  = float(request.args.get("gx", 0))
        gy  = float(request.args.get("gy", 0))
        gz  = float(request.args.get("gz", 0))

        # Magnitude already in g (ESP32 already converted)
        magnitude = math.sqrt(ax**2 + ay**2 + az**2)

        # Accident detection
        accident = (magnitude > ACCIDENT_THRESHOLD or
                    magnitude < FREEFALL_THRESHOLD)

        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Build payload matching frontend expectations
        cnt = request.args.get("cnt", "0")
        payload = {
            "gps": {
                "lat": float(lat) if lat and lat != "0" else None,
                "lon": float(lon) if lon and lon != "0" else None
            },
            "mpu6050": {
                "ax":        round(ax, 3),
                "ay":        round(ay, 3),
                "az":        round(az, 3),
                "gx":        round(gx, 3),
                "gy":        round(gy, 3),
                "gz":        round(gz, 3),
                "magnitude": round(magnitude, 3)
            },
            "accident":  accident,
            "timestamp": ts,
            "status":    "accident" if accident else "safe",
            "counter":   int(cnt)   # ESP32 send counter — frontend detects new data
        }

        # Write live data to Firebase /live (overwrites)
        fb_put("live", payload)

        # If accident — also save to /accidents (permanent history)
        if accident:
            accident_record = {
                "lat":       float(lat) if lat and lat != "0" else None,
                "lon":       float(lon) if lon and lon != "0" else None,
                "magnitude": round(magnitude, 3),
                "ax": round(ax,3), "ay": round(ay,3), "az": round(az,3),
                "timestamp": ts
            }
            fb_post("accidents", accident_record)
            print(f"🚨 ACCIDENT → Firebase | {magnitude:.3f}g | GPS:{lat},{lon}")

        print(f"📡 [{ts}] {('ACCIDENT' if accident else 'safe').upper()} | "
              f"{magnitude:.3f}g | GPS:{lat},{lon}")

        return jsonify({"status": "ok"}), 200

    except Exception as e:
        print(f"❌ ERROR: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({"status": "running",
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}), 200

if __name__ == '__main__':
    print("🚀 VehicleGuard Backend")
    print(f"   Firebase : {FIREBASE_URL}")
    print(f"   Accident : >{ACCIDENT_THRESHOLD}g | Freefall: <{FREEFALL_THRESHOLD}g")
    app.run(host='0.0.0.0', port=5000, debug=False)
