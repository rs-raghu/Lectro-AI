import os
import sounddevice as sd
import numpy as np
import wave
from flask import Flask, request, jsonify
from threading import Thread

# Base recordings folder
BASE_RECORDINGS_FOLDER = os.path.abspath("recordings")
os.makedirs(BASE_RECORDINGS_FOLDER, exist_ok=True)

app = Flask(__name__)

# Recording settings
SAMPLE_RATE = 44100
CHANNELS = 1
RECORDING = []
RECORDING_ACTIVE = False
CURRENT_TEACHER_ID = None

# Status tracking variable
SERVER_STATUS = "Idle"  # Possible values: "Idle", "Connected to ESP32", "Receiving Request", "Recording Audio"

def get_next_filename(teacher_id):
    """Generate the next available filename for a teacher's recordings."""
    teacher_folder = os.path.join(BASE_RECORDINGS_FOLDER, teacher_id)
    os.makedirs(teacher_folder, exist_ok=True)
    
    i = 1
    while os.path.exists(os.path.join(teacher_folder, f"{teacher_id}{i}.wav")):
        i += 1
    
    return os.path.join(teacher_folder, f"{teacher_id}{i}.wav")

def start_recording():
    """Start recording audio."""
    global RECORDING, RECORDING_ACTIVE, SERVER_STATUS
    RECORDING = []
    RECORDING_ACTIVE = True
    SERVER_STATUS = "Recording Audio"
    
    def callback(indata, frames, time, status):
        if RECORDING_ACTIVE:
            RECORDING.append(indata.copy())
    
    with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, callback=callback):
        while RECORDING_ACTIVE:
            sd.sleep(100)
    
    SERVER_STATUS = "Idle"

def stop_recording():
    """Stop recording and save audio to file."""
    global RECORDING_ACTIVE, CURRENT_TEACHER_ID, SERVER_STATUS
    RECORDING_ACTIVE = False
    
    if RECORDING and CURRENT_TEACHER_ID:
        audio_data = np.concatenate(RECORDING, axis=0)
        file_path = get_next_filename(CURRENT_TEACHER_ID)
        
        with wave.open(file_path, "wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes((audio_data * 32767).astype(np.int16).tobytes())
        
        print(f"[Recorder] Audio saved at: {file_path}")
        SERVER_STATUS = f"Audio saved at {file_path}"
        return file_path
    
    SERVER_STATUS = "Idle"
    return None

@app.route("/start", methods=["POST"])
def start_recording_api():
    """API to start recording."""
    global CURRENT_TEACHER_ID, SERVER_STATUS
    data = request.get_json()
    
    if not data or "uid" not in data:
        SERVER_STATUS = "Invalid Request from ESP32"
        return jsonify({"error": "Invalid request"}), 400
    
    CURRENT_TEACHER_ID = data["uid"]
    SERVER_STATUS = f"Connected to ESP32 | UID: {CURRENT_TEACHER_ID}"
    
    Thread(target=start_recording).start()
    print(f"[Flask] Recording started for UID: {CURRENT_TEACHER_ID}")
    
    SERVER_STATUS = f"Receiving Request | Recording Started for UID: {CURRENT_TEACHER_ID}"
    
    return jsonify({"message": "Recording started", "uid": CURRENT_TEACHER_ID}), 200

@app.route("/stop", methods=["POST"])
def stop_recording_api():
    """API to stop recording."""
    global CURRENT_TEACHER_ID, SERVER_STATUS
    data = request.get_json()

    if not data or "uid" not in data:
        SERVER_STATUS = "Invalid Request from ESP32"
        return jsonify({"error": "Invalid request"}), 400

    file_path = stop_recording()
    
    if file_path:
        print(f"[Flask] Recording stopped and saved at: {file_path}")
        SERVER_STATUS = f"Recording Stopped | File Saved: {file_path}"
        return jsonify({
            "message": "Recording stopped",
            "file": file_path
        }), 200

    SERVER_STATUS = "No Active Recording Found"
    
    return jsonify({"error": "No recording found"}), 500

@app.route("/status", methods=["GET"])
def status_api():
    """API to get server status."""
    global SERVER_STATUS
    return jsonify({"status": SERVER_STATUS}), 200

@app.route("/", methods=["GET"])
def homepage():
    """Webpage to display server status."""
    global SERVER_STATUS
    
    html_content = f"""
        <html>
        <head>
            <title>Flask Server Status</title>
            <meta http-equiv="refresh" content="2"> <!-- Auto-refresh every 2 seconds -->
        </head>
        <body>
            <h1>Flask Server Status</h1>
            <p><b>Status:</b> {SERVER_STATUS}</p>
            <p><b>Current Teacher ID:</b> {CURRENT_TEACHER_ID if CURRENT_TEACHER_ID else 'None'}</p>
            <p><b>Recording Active:</b> {"Yes" if RECORDING_ACTIVE else "No"}</p>
        </body>
        </html>
    """
    
    return html_content

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
