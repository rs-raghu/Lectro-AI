"""
watch_dog.py — Automatic transcription and summarization pipeline

Watches recordings/ for new .wav files → transcribes with Whisper → saves to transcripts/
Watches transcripts/ for new .txt files → summarizes with Ollama Mistral → saves to summarize/

Setup:
    pip install watchdog openai-whisper python-dotenv
    Install Ollama from https://ollama.com and run: ollama pull mistral
    Copy .env.example → .env and set OLLAMA_PATH if needed.
    Run: python watch_dog.py
"""

import os
import time
import subprocess
from dotenv import load_dotenv
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

load_dotenv()

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
OLLAMA_PATH        = os.getenv("OLLAMA_PATH", "ollama")   # use system PATH by default
RECORDINGS_FOLDER  = os.path.abspath("recordings")
TRANSCRIPTS_FOLDER = os.path.abspath("transcripts")
SUMMARIZE_FOLDER   = os.path.abspath("summarize")
SUMMARIZE_TIMEOUT  = 180   # seconds before giving up on Ollama

for folder in (RECORDINGS_FOLDER, TRANSCRIPTS_FOLDER, SUMMARIZE_FOLDER):
    os.makedirs(folder, exist_ok=True)

# ---------------------------------------------------------------------------
# Load Whisper model once at startup (not on every scan)
# ---------------------------------------------------------------------------
print("[Watchdog] Loading Whisper model — this may take a moment...")
import whisper   # imported after dotenv so PATH is set
model = whisper.load_model("turbo")
print("[Watchdog] Whisper ready.")

# ---------------------------------------------------------------------------
# Event handler
# ---------------------------------------------------------------------------
class FileHandler(FileSystemEventHandler):

    def on_created(self, event):
        if event.is_directory:
            return

        abs_path = os.path.abspath(event.src_path)

        if abs_path.endswith(".wav"):
            # Give the server a moment to finish writing the file
            time.sleep(2)
            print(f"[Watchdog] New audio detected: {abs_path}")
            self._transcribe(abs_path)

        elif abs_path.endswith(".txt") and abs_path.startswith(TRANSCRIPTS_FOLDER):
            time.sleep(1)
            print(f"[Watchdog] New transcript detected: {abs_path}")
            self._summarize(abs_path)

    # -----------------------------------------------------------------------

    def _transcribe(self, audio_path: str):
        """Transcribe a .wav file with Whisper and save the result to transcripts/."""
        try:
            base    = os.path.splitext(os.path.basename(audio_path))[0]
            out_path = os.path.join(TRANSCRIPTS_FOLDER, f"{base}.txt")

            # Skip if transcript already exists (e.g. watchdog restart)
            if os.path.exists(out_path):
                print(f"[Transcriber] Already transcribed, skipping: {out_path}")
                return

            print(f"[Transcriber] Processing: {audio_path}")
            result     = model.transcribe(audio_path, condition_on_previous_text=False)
            transcript = result["text"].strip()

            if not transcript:
                print("[Transcriber] Whisper returned empty result — skipping.")
                return

            with open(out_path, "w", encoding="utf-8") as f:
                f.write(transcript)
            print(f"[Transcriber] Saved: {out_path}")

        except Exception as e:
            print(f"[Transcriber] ERROR: {e}")

    # -----------------------------------------------------------------------

    def _summarize(self, input_path: str):
        """Summarize a transcript with Ollama Mistral and save to summarize/."""
        try:
            base     = os.path.splitext(os.path.basename(input_path))[0]
            out_path = os.path.join(SUMMARIZE_FOLDER, f"{base}.txt")

            if os.path.exists(out_path):
                print(f"[Summarizer] Already summarized, skipping: {out_path}")
                return

            with open(input_path, "r", encoding="utf-8") as f:
                transcript = f.read().strip()

            if not transcript:
                print("[Summarizer] Transcript is empty — skipping.")
                return

            print(f"[Summarizer] Summarizing via Ollama: {input_path}")
            prompt = (
                "You are a note-taking assistant. "
                "Summarize the following lecture transcript into clear, concise bullet points "
                "covering the key topics and takeaways:\n\n" + transcript
            )

            result = subprocess.run(
                [OLLAMA_PATH, "run", "mistral", prompt],
                capture_output=True,
                text=True,
                timeout=SUMMARIZE_TIMEOUT,
            )

            if result.returncode != 0:
                print(f"[Summarizer] Ollama exited with error:\n{result.stderr.strip()}")
                return

            summary = result.stdout.strip()
            if not summary:
                print("[Summarizer] Ollama returned empty output — skipping.")
                return

            with open(out_path, "w", encoding="utf-8") as f:
                f.write(summary)
            print(f"[Summarizer] Saved: {out_path}")

        except subprocess.TimeoutExpired:
            print(f"[Summarizer] Timed out after {SUMMARIZE_TIMEOUT}s — check Ollama.")
        except FileNotFoundError:
            print(f"[Summarizer] Ollama not found at '{OLLAMA_PATH}'. "
                  "Set OLLAMA_PATH in .env or ensure 'ollama' is in your system PATH.")
        except Exception as e:
            print(f"[Summarizer] ERROR: {e}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    handler  = FileHandler()
    observer = Observer()
    observer.schedule(handler, RECORDINGS_FOLDER,  recursive=True)
    observer.schedule(handler, TRANSCRIPTS_FOLDER, recursive=True)
    observer.start()

    print(f"[Watchdog] Monitoring:\n  {RECORDINGS_FOLDER}\n  {TRANSCRIPTS_FOLDER}")
    print("[Watchdog] Press Ctrl+C to stop.\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[Watchdog] Shutting down...")
        observer.stop()
    observer.join()
    print("[Watchdog] Stopped.")
