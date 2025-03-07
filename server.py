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
    global RECORDING, RECORDING_ACTIVE
    RECORDING = []
    RECORDING_ACTIVE = True
    
    def callback(indata, frames, time, status):
        if RECORDING_ACTIVE:
            RECORDING.append(indata.copy())
    
    with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, callback=callback):
        while RECORDING_ACTIVE:
            sd.sleep(100)

def stop_recording():
    """Stop recording and save audio to file."""
    global RECORDING_ACTIVE, CURRENT_TEACHER_ID
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
        return file_path
    return None

@app.route("/start", methods=["POST"])
def start_recording_api():
    """API to start recording."""
    global CURRENT_TEACHER_ID
    data = request.get_json()
    if not data or "uid" not in data:
        return jsonify({"error": "Invalid request"}), 400
    
    CURRENT_TEACHER_ID = data["uid"]
    Thread(target=start_recording).start()
    print(f"[Flask] Recording started for UID: {CURRENT_TEACHER_ID}")
    return jsonify({"message": "Recording started", "uid": CURRENT_TEACHER_ID}), 200

@app.route("/stop", methods=["POST"])
def stop_recording_api():
    """API to stop recording."""
    global CURRENT_TEACHER_ID
    data = request.get_json()

    if not data or "uid" not in data:
        return jsonify({"error": "Invalid request"}), 400

    file_path = stop_recording()
    if file_path:
        print(f"[Flask] Recording stopped and saved at: {file_path}")
        return jsonify({
            "message": "Recording stopped",
            "file": file_path
        }), 200

    return jsonify({"error": "No recording found"}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)