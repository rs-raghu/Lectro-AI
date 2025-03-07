import os
import sounddevice as sd
import numpy as np
import wave
from flask import Flask, request, jsonify
from threading import Thread

# Folders
RECORDINGS_FOLDER = os.path.abspath("recordings")
os.makedirs(RECORDINGS_FOLDER, exist_ok=True)

app = Flask(__name__)

# Recording settings
SAMPLE_RATE = 44100
CHANNELS = 1
RECORDING = []
RECORDING_ACTIVE = False

def get_next_filename():
    """Generate the next available filename for recordings."""
    i = 1
    while os.path.exists(os.path.join(RECORDINGS_FOLDER, f"recording{i}.wav")):
        i += 1
    return os.path.join(RECORDINGS_FOLDER, f"recording{i}.wav")

def start_recording():
    """Start recording audio."""
    global RECORDING, RECORDING_ACTIVE
    RECORDING = []
    RECORDING_ACTIVE = True
    
    def callback(indata, frames, time, status):
        if status:
            print(f"[Error] {status}")  # Log sounddevice errors
        if RECORDING_ACTIVE:
            RECORDING.append(indata.copy())

    try:
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, callback=callback):
            while RECORDING_ACTIVE:
                sd.sleep(100)
    except Exception as e:
        print(f"[Error] SoundDevice issue: {e}")

def stop_recording():
    """Stop recording and save audio to file."""
    global RECORDING_ACTIVE
    RECORDING_ACTIVE = False
    
    if RECORDING:
        audio_data = np.concatenate(RECORDING, axis=0)

        # Convert to int16 correctly
        audio_data = (audio_data * 32767).astype(np.int16)

        file_path = get_next_filename()
        
        with wave.open(file_path, "wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(2)  # Corrected: Matches int16 format
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(audio_data.tobytes())
        
        print(f"[Recorder] Audio saved at: {file_path}")
        return file_path
    return None

@app.route("/start", methods=["POST"])
def start_recording_api():
    """API to start recording."""
    Thread(target=start_recording).start()
    print(f"[Flask] Recording started. Files will be saved in: {RECORDINGS_FOLDER}")
    return jsonify({"message": "Recording started"}), 200

@app.route("/stop", methods=["POST"])
def stop_recording_api():
    """API to stop recording."""
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
