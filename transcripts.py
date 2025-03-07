import os
import time
import requests
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# AssemblyAI API Key
ASSEMBLYAI_API_KEY = "dcb01ee711954ebd96ea9f9e76c9f3c0"  # Replace with your actual API key
UPLOAD_URL = "https://api.assemblyai.com/v2/upload"
TRANSCRIBE_URL = "https://api.assemblyai.com/v2/transcript"

# Folders
RECORDINGS_FOLDER = os.path.abspath("recordings")
TRANSCRIPTS_FOLDER = os.path.abspath("transcripts")

# Ensure necessary folders exist
os.makedirs(RECORDINGS_FOLDER, exist_ok=True)
os.makedirs(TRANSCRIPTS_FOLDER, exist_ok=True)

class AudioHandler(FileSystemEventHandler):
    """Watches for new audio files and transcribes them automatically"""

    def on_created(self, event):
        if event.is_directory:
            return
        
        file_path = event.src_path
        if file_path.endswith(".wav"):
            print(f"[Watcher] New file detected: {file_path}")
            transcript_text = transcribe_audio(file_path)

            if transcript_text:
                save_transcript(file_path, transcript_text)

def upload_audio(file_path):
    """Uploads audio file to AssemblyAI"""
    headers = {'authorization': ASSEMBLYAI_API_KEY}
    
    with open(file_path, "rb") as f:
        response = requests.post(UPLOAD_URL, headers=headers, files={"file": f})
    
    if response.status_code == 200:
        return response.json()["upload_url"]
    else:
        print("[ERROR] Upload failed:", response.text)
        return None

def transcribe_audio(file_path):
    """Sends audio to AssemblyAI and fetches transcription"""
    upload_url = upload_audio(file_path)
    if not upload_url:
        return None

    headers = {'authorization': ASSEMBLYAI_API_KEY, 'content-type': 'application/json'}
    data = {"audio_url": upload_url}
    response = requests.post(TRANSCRIBE_URL, json=data, headers=headers)

    if response.status_code == 200:
        transcript_id = response.json()["id"]
        print(f"[INFO] Transcription started for {file_path}...")

        # Wait for transcription to complete
        while True:
            status_response = requests.get(f"{TRANSCRIBE_URL}/{transcript_id}", headers=headers)
            status = status_response.json()
            
            if status["status"] == "completed":
                transcript_text = status["text"]
                print(f"[INFO] Transcription complete for {file_path}")
                return transcript_text
            
            elif status["status"] == "failed":
                print(f"[ERROR] Transcription failed for {file_path}")
                return None

            time.sleep(5)  # Check every 5 seconds

    else:
        print("[ERROR] Transcription request failed:", response.text)
        return None

def save_transcript(file_path, transcript_text):
    """Saves transcription to a text file"""
    transcript_filename = os.path.basename(file_path) + ".txt"
    transcript_path = os.path.join(TRANSCRIPTS_FOLDER, transcript_filename)

    with open(transcript_path, "w", encoding="utf-8") as f:
        f.write(transcript_text)

    print(f"[INFO] Transcript saved: {transcript_path}")

def watch_folder():
    """Watches the recordings folder for new files"""
    event_handler = AudioHandler()
    observer = Observer()
    observer.schedule(event_handler, RECORDINGS_FOLDER, recursive=False)
    observer.start()

    print("[Watcher] Watching for new recordings...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == "__main__":
    watch_folder()
