"""
server.py — Flask recording server

Receives /start and /stop from the ESP32, records audio via sounddevice,
and saves .wav files named  uid_YYYYMMDD_HHMMSS.wav  inside recordings/<uid>/.

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
from datetime import datetime

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
    "start_time": None,   # datetime captured at /start — used for filename
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
def build_filename(teacher_id: str, start_time: datetime) -> str:
    """
    Build a path like:
        recordings/53cb1229/53cb1229_20260329_220513.wav
    The timestamp is the moment recording STARTED, not when it was saved.
    """
    folder = os.path.join(BASE_RECORDINGS_FOLDER, teacher_id)
    os.makedirs(folder, exist_ok=True)
    timestamp = start_time.strftime("%Y%m%d_%H%M%S")
    return os.path.join(folder, f"{teacher_id}_{timestamp}.wav")

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
        frames      = list(_state["frames"])
        teacher_id  = _state["teacher_id"]
        start_time  = _state["start_time"]

    if not frames or not teacher_id or not start_time:
        return None

    audio = np.concatenate(frames, axis=0)
    path  = build_filename(teacher_id, start_time)

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
        _state["start_time"] = datetime.now()
        _state["status"]     = f"Recording | UID: {uid}"

    Thread(target=_record_thread, daemon=True).start()
    print(f"[Server] Recording started — UID: {uid}")
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
        if _state["teacher_id"] != uid:
            return jsonify({"error": "UID mismatch — this card did not start the session"}), 403
        _state["active"] = False
        _state["status"] = "Saving..."

    file_path = _save_recording()

    with _lock:
        _state["teacher_id"] = None
        _state["start_time"] = None
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
    """Unauthenticated read-only endpoint — polled by the dashboard JS."""
    with _lock:
        return jsonify({
            "status":     _state["status"],
            "recording":  _state["active"],
            "teacher_id": _state["teacher_id"] or "—",
        }), 200


@app.route("/", methods=["GET"])
def homepage():
    """Live dashboard — all fields update every 2 s via JS fetch, no page reload needed."""
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
  body{{font-family:sans-serif;max-width:500px;margin:2rem auto;padding:0 1rem}}
  h2{{margin-bottom:1rem}}
  .row{{display:flex;justify-content:space-between;align-items:center;
        padding:10px 0;border-bottom:1px solid #e5e7eb}}
  .label{{color:#6b7280;font-size:.9rem}}
  .badge{{padding:3px 12px;border-radius:10px;font-size:.85rem;font-weight:600}}
  .on{{background:#d1fae5;color:#065f46}}
  .off{{background:#f3f4f6;color:#374151}}
  .dot{{width:8px;height:8px;border-radius:50%;display:inline-block;margin-right:6px}}
  .dot-on{{background:#10b981}} .dot-off{{background:#9ca3af}}
</style>
<script>
async function refresh() {{
  try {{
    const d = await (await fetch('/status')).json();
    document.getElementById('uid').textContent    = d.teacher_id;
    document.getElementById('status-text').textContent = d.status;
    const badge = document.getElementById('badge');
    const dot   = document.getElementById('dot');
    badge.textContent = d.recording ? 'Recording' : 'Idle';
    badge.className   = 'badge ' + (d.recording ? 'on' : 'off');
    dot.className     = 'dot '  + (d.recording ? 'dot-on' : 'dot-off');
  }} catch(e) {{}}
}}
setInterval(refresh, 2000);
refresh();
</script>
</head><body>
<h2>Recording Server</h2>
<div class="row">
  <span class="label">Status</span>
  <span id="status-text">{status}</span>
</div>
<div class="row">
  <span class="label">Teacher UID</span>
  <b id="uid">{teacher_id}</b>
</div>
<div class="row">
  <span class="label">Recording</span>
  <span>
    <span id="dot" class="dot {'dot-on' if active else 'dot-off'}"></span>
    <span id="badge" class="badge {badge_class}">{badge_label}</span>
  </span>
</div>
</body></html>"""


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # debug=False — the reloader would spawn a second process and open a
    # competing audio stream.
    app.run(host="0.0.0.0", port=5000, debug=False)