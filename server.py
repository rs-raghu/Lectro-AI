import sounddevice as sd
import numpy as np
import wave
import threading
import time
import os
from flask import Flask, jsonify, request

app = Flask(__name__)

# Global variables
is_recording = False
last_scanned_uid = "None"
recording_thread = None
recorded_audio = []
RECORDINGS_DIR = "recordings"

# Function to record audio
def record_audio():
    """Continuously records audio while is_recording is True."""
    global recorded_audio
    
    with sd.InputStream(samplerate=44100, channels=1, dtype=np.int16) as stream:
        while is_recording:
            data, overflowed = stream.read(1024)
            recorded_audio.append(data)
            time.sleep(0.01)

@app.route("/", methods=["GET"])
def home():
    """Check if the Flask server is running."""
    return jsonify({"message": "Flask server is running!"})

@app.route("/start", methods=["POST"])
def start_recording():
    """Starts recording when an RFID card is scanned."""
    global is_recording, last_scanned_uid, recording_thread, recorded_audio

    data = request.get_json()
    last_scanned_uid = data.get("uid", "Unknown")

    if not is_recording:
        is_recording = True
        recorded_audio = []  # Clear previous data
        recording_thread = threading.Thread(target=record_audio)
        recording_thread.start()

    return jsonify({"status": "Recording started", "uid": last_scanned_uid})

@app.route("/stop", methods=["POST"])
def stop_recording():
    """Stops recording and saves the file."""
    global is_recording

    is_recording = False
    
    if recording_thread:
        recording_thread.join()  # Ensure the thread stops before proceeding

    if recorded_audio:
        save_audio_file()

    return jsonify({"status": "Recording stopped", "uid": last_scanned_uid})

def save_audio_file():
    """Saves recorded audio with proper volume normalization."""
    global recorded_audio, last_scanned_uid

    if not recorded_audio:
        print("[Error] No audio data recorded.")
        return

    if not os.path.exists(RECORDINGS_DIR):
        os.makedirs(RECORDINGS_DIR)

    base_filename = f"{last_scanned_uid}.wav"
    filepath = os.path.join(RECORDINGS_DIR, base_filename)

    if os.path.exists(filepath):
        counter = 1
        while os.path.exists(os.path.join(RECORDINGS_DIR, f"{last_scanned_uid}_{counter}.wav")):
            counter += 1
        filepath = os.path.join(RECORDINGS_DIR, f"{last_scanned_uid}_{counter}.wav")

    try:
        # Convert recorded data into numpy array
        audio_data = np.concatenate(recorded_audio, axis=0)

        # Normalize to full range (-32768 to 32767)
        audio_data = np.int16(audio_data * (32767 / max(1, np.max(np.abs(audio_data)))))

        with wave.open(filepath, 'wb') as wf:
            wf.setnchannels(1)        # Mono
            wf.setsampwidth(2)        # 16-bit
            wf.setframerate(44100)    # 44.1 kHz
            wf.writeframes(audio_data.tobytes())

        print(f"[Server] Audio saved successfully: {filepath}")

    except Exception as e:
        print(f"[Error] Could not save audio: {e}")



@app.route("/status", methods=["GET"])
def get_status():
    """Check the current recording status."""
    return jsonify({"recording": is_recording, "uid": last_scanned_uid})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
