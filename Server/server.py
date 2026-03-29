"""
server.py — Flask recording server

Receives /start and /stop from the ESP32, records audio via sounddevice,
and saves .wav files organised by teacher UID.

Setup:
    pip install flask sounddevice numpy python-dotenv
    Copy .env.example → .env and set FLASK_AUTH_TOKEN.
    Run: python server.py
"""

import os
import wave
import numpy as np
import sounddevice as sd
from flask import Flask, request, jsonify
from threading import Thread, Lock
from functools import wraps
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
AUTH_TOKEN             = os.getenv("FLASK_AUTH_TOKEN", "")
BASE_RECORDINGS_FOLDER = os.path.abspath("recordings")
SAMPLE_RATE            = 44100
CHANNELS               = 1

os.makedirs(BASE_RECORDINGS_FOLDER, exist_ok=True)

if not AUTH_TOKEN:
    print("[WARNING] FLASK_AUTH_TOKEN is not set in .env — all requests will be rejected.")

# ---------------------------------------------------------------------------
# App & shared state
# ---------------------------------------------------------------------------
app = Flask(__name__)

_lock = Lock()
_state = {
    "active":     False,
    "frames":     [],
    "teacher_id": None,
    "status":     "Idle",
}

# ---------------------------------------------------------------------------
# Auth decorator
# ---------------------------------------------------------------------------
def require_auth(f):
    """Reject requests that don't carry the correct X-Auth-Token header."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get("X-Auth-Token", "")
        if not AUTH_TOKEN or token != AUTH_TOKEN:
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated

# ---------------------------------------------------------------------------
# File helpers
# ---------------------------------------------------------------------------
def get_next_filename(teacher_id: str) -> str:
    """Return the next non-existing path like recordings/<uid>/<uid>3.wav."""
    folder = os.path.join(BASE_RECORDINGS_FOLDER, teacher_id)
    os.makedirs(folder, exist_ok=True)
    i = 1
    while os.path.exists(os.path.join(folder, f"{teacher_id}{i}.wav")):
        i += 1
    return os.path.join(folder, f"{teacher_id}{i}.wav")

# ---------------------------------------------------------------------------
# Audio recording (runs in a background thread)
# ---------------------------------------------------------------------------
def _record_thread():
    """Appends incoming audio frames to _state['frames'] until deactivated."""
    def callback(indata, frames, time, status):
        with _lock:
            if _state["active"]:
                _state["frames"].append(indata.copy())

    with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, callback=callback):
        while True:
            with _lock:
                if not _state["active"]:
                    break
            sd.sleep(100)

def _save_recording() -> str | None:
    """Concatenate buffered frames and write to disk. Returns the file path or None."""
    with _lock:
        frames     = list(_state["frames"])
        teacher_id = _state["teacher_id"]

    if not frames or not teacher_id:
        return None

    audio = np.concatenate(frames, axis=0)
    path  = get_next_filename(teacher_id)

    with wave.open(path, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)          # 16-bit
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes((audio * 32767).astype(np.int16).tobytes())

    return path

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/start", methods=["POST"])
@require_auth
def start_recording_api():
    data = request.get_json()
    if not data or "uid" not in data:
        return jsonify({"error": "Missing uid in request body"}), 400

    uid = data["uid"]

    with _lock:
        if _state["active"]:
            return jsonify({"error": "Recording already active", "uid": _state["teacher_id"]}), 409
        _state["active"]     = True
        _state["frames"]     = []
        _state["teacher_id"] = uid
        _state["status"]     = f"Recording | UID: {uid}"

    Thread(target=_record_thread, daemon=True).start()
    print(f"[Server] Recording started for UID: {uid}")
    return jsonify({"message": "Recording started", "uid": uid}), 200


@app.route("/stop", methods=["POST"])
@require_auth
def stop_recording_api():
    data = request.get_json()
    if not data or "uid" not in data:
        return jsonify({"error": "Missing uid in request body"}), 400

    uid = data["uid"]

    with _lock:
        if not _state["active"]:
            return jsonify({"error": "No recording is currently active"}), 409

        # Only the card that started the session can stop it
        if _state["teacher_id"] != uid:
            return jsonify({"error": "UID mismatch — this card did not start the session"}), 403

        _state["active"] = False
        _state["status"] = "Saving..."

    file_path = _save_recording()

    with _lock:
        _state["teacher_id"] = None
        if file_path:
            _state["status"] = f"Saved: {os.path.basename(file_path)}"
        else:
            _state["status"] = "Save failed — no audio captured"

    if file_path:
        print(f"[Server] Saved: {file_path}")
        return jsonify({"message": "Recording stopped", "file": file_path}), 200

    return jsonify({"error": "No audio data was captured"}), 500


@app.route("/status", methods=["GET"])
def status_api():
    """Unauthenticated read-only endpoint for dashboards and health checks."""
    with _lock:
        return jsonify({
            "status":     _state["status"],
            "recording":  _state["active"],
            "teacher_id": _state["teacher_id"],
        }), 200


@app.route("/", methods=["GET"])
def homepage():
    """Simple auto-refreshing dashboard — open in any browser on the same network."""
    with _lock:
        status     = _state["status"]
        teacher_id = _state["teacher_id"] or "—"
        active     = _state["active"]

    badge_class = "on" if active else "off"
    badge_label = "Recording" if active else "Idle"

    return f"""<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Recording Server</title>
<style>
  body{{font-family:sans-serif;max-width:480px;margin:2rem auto;padding:0 1rem}}
  .row{{display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #eee}}
  .badge{{padding:3px 10px;border-radius:10px;font-size:.85rem;font-weight:600}}
  .on{{background:#d1fae5;color:#065f46}} .off{{background:#f3f4f6;color:#374151}}
</style>
<script>
async function refresh() {{
  const d = await (await fetch('/status')).json();
  document.getElementById('status').textContent  = d.status;
  document.getElementById('uid').textContent     = d.teacher_id ?? '—';
  const b = document.getElementById('badge');
  b.textContent = d.recording ? 'Recording' : 'Idle';
  b.className   = 'badge ' + (d.recording ? 'on' : 'off');
}}
setInterval(refresh, 2000);
</script>
</head><body>
<h2>Recording Server</h2>
<div class="row"><span>Status</span><span>{status}</span></div>
<div class="row"><span>Teacher UID</span><b id="uid">{teacher_id}</b></div>
<div class="row"><span>Recording</span><span id="badge" class="badge {badge_class}">{badge_label}</span></div>
</body></html>"""


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # debug=False is important — Flask's reloader spawns a second process which
    # would open a second audio stream and cause conflicts.
    app.run(host="0.0.0.0", port=5000, debug=False)
