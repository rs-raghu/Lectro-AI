import os
import time
import subprocess
import sys
import whisper
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Load Whisper model (optimized for speed)
model = whisper.load_model("turbo")  # Change to "base", "small", etc., if needed

# Path to Ollama executable
OLLAMA_PATH = r"C:/Users/raghu/AppData/Local/Programs/Ollama/ollama.exe"  # Update if needed

# Folders to monitor and save files
RECORDINGS_FOLDER = os.path.abspath("recordings")
TRANSCRIPTS_FOLDER = os.path.abspath("transcripts")
SUMMARIZE_FOLDER = os.path.abspath("summarize")

# Ensure required folders exist
os.makedirs(RECORDINGS_FOLDER, exist_ok=True)
os.makedirs(TRANSCRIPTS_FOLDER, exist_ok=True)
os.makedirs(SUMMARIZE_FOLDER, exist_ok=True)


class FileHandler(FileSystemEventHandler):
    def on_created(self, event):
        """Detects new files and processes them accordingly."""
        if event.is_directory:
            return

        file_path = event.src_path

        # Handle new audio file (.wav) → Transcription
        if file_path.endswith(".wav"):
            time.sleep(2)  # Ensure file is fully written
            print(f"[Watchdog] New audio file detected: {file_path}")
            self.transcribe_audio(file_path)

        # Handle new transcript file (.txt) → Summarization
        elif file_path.endswith(".txt") and TRANSCRIPTS_FOLDER in file_path:
            time.sleep(2)  # Ensure file is fully written
            print(f"[Watchdog] New transcript detected: {file_path}")
            self.summarize_text(file_path)

    def transcribe_audio(self, audio_path):
        """Transcribes an audio file using Whisper and saves the transcript."""
        print(f"[Transcriber] Processing: {audio_path}")

        try:
            # Extract filename (without extension)
            base_filename = os.path.splitext(os.path.basename(audio_path))[0]

            # Transcribe audio
            result = model.transcribe(audio_path, condition_on_previous_text=False)
            transcript = result["text"].strip()

            if not transcript:
                print("[Warning] No transcription generated.")
                return

            # Save transcript in the transcripts folder
            transcript_filename = os.path.join(TRANSCRIPTS_FOLDER, f"{base_filename}.txt")

            with open(transcript_filename, "w", encoding="utf-8") as f:
                f.write(transcript)

            print(f"[Transcriber] Transcript saved: {transcript_filename}")

        except Exception as e:
            print(f"[Error] Transcription failed: {e}")

    def summarize_text(self, input_file):
        """Summarizes a transcript file using the local Ollama Mistral model."""
        print(f"[Summarizer] Summarizing: {input_file}")

        try:
            # Extract filename without extension
            base_filename = os.path.splitext(os.path.basename(input_file))[0]
            output_file = os.path.join(SUMMARIZE_FOLDER, f"{base_filename}.txt")

            # Read transcript
            with open(input_file, "r", encoding="utf-8") as f:
                transcript = f.read().strip()

            if not transcript:
                print("[Warning] Transcript is empty. Skipping summarization.")
                return

            # Call Ollama's Mistral model
            result = subprocess.run(
                [OLLAMA_PATH, "run", "mistral", f"Summarize this text: {transcript}"],
                capture_output=True,
                text=True
            )

            summary = result.stdout.strip()

            # Save summary
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(summary)

            print(f"[Summarizer] Summary saved: {output_file}")

        except Exception as e:
            print(f"[Error] Summarization failed: {e}")


if __name__ == "__main__":
    event_handler = FileHandler()
    observer = Observer()
    observer.schedule(event_handler, RECORDINGS_FOLDER, recursive=True)
    observer.schedule(event_handler, TRANSCRIPTS_FOLDER, recursive=True)
    observer.start()

    print("[Watchdog] Monitoring 'recordings/' and 'transcripts/' for new files...")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[Watchdog] Stopping...")
        observer.stop()
    
    observer.join()
