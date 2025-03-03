import sounddevice as sd
import numpy as np
import wave
import threading
import time
from flask import Flask, jsonify, request

app = Flask(__name__)

is_recording = False
last_scanned_uid = "None"
recording_thread = None
recorded_audio = []

def record_audio():
    global recorded_audio
    print("🎤 Audio recording started...")
    
    with sd.InputStream(samplerate=44100, channels=1, dtype=np.int16) as stream:
        while is_recording:
            data, overflowed = stream.read(1024)
            recorded_audio.append(data)
            time.sleep(0.01)

@app.route('/start', methods=['POST'])
def start_recording():
    global is_recording, last_scanned_uid, recording_thread, recorded_audio
    
    data = request.get_json()
    last_scanned_uid = data.get("uid", "Unknown")

    if not is_recording:
        is_recording = True
        recorded_audio = []  # Clear previous audio data
        recording_thread = threading.Thread(target=record_audio)
        recording_thread.start()
        print(f"✅ Recording started for UID: {last_scanned_uid}")
    return jsonify({"status": "Recording started", "uid": last_scanned_uid})

@app.route('/stop', methods=['POST'])
def stop_recording():
    global is_recording
    is_recording = False
    
    if recording_thread:
        recording_thread.join()

    print("🛑 Recording stopped. Saving file...")

    if recorded_audio:
        save_audio_file()

    return jsonify({"status": "Recording stopped", "uid": last_scanned_uid})

def save_audio_file():
    global recorded_audio, last_scanned_uid

    filename = f"{last_scanned_uid}.wav"
    filepath = f"recordings/{filename}"

    # Convert list of numpy arrays to bytes
    audio_data = np.concatenate(recorded_audio, axis=0)

    with wave.open(filepath, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(44100)
        wf.writeframes(audio_data.tobytes())

    print(f"✅ Audio saved as {filepath}")

@app.route('/status', methods=['GET'])
def get_status():
    return jsonify({"recording": is_recording, "uid": last_scanned_uid})

if __name__ == '__main__':
    import os
    if not os.path.exists("recordings"):
        os.makedirs("recordings")

    app.run(host='0.0.0.0', port=5000, debug=True)
