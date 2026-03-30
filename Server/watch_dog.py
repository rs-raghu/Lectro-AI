"""
watch_dog.py — Automatic transcription and summarization pipeline

Watches recordings/ for new .wav files → transcribes with Whisper → saves to transcripts/
Watches transcripts/ for new .txt files → summarizes with Gemini API → saves to summarize/

Setup:
    pip install watchdog openai-whisper python-dotenv google-generativeai
    Add GEMINI_API_KEY to your .env file.
    Get a free API key at: https://aistudio.google.com/app/apikey
    Run: python watch_dog.py
"""

import os
import time
from dotenv import load_dotenv
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import google.generativeai as genai

load_dotenv()

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
GEMINI_API_KEY     = os.getenv("GEMINI_API_KEY", "")
RECORDINGS_FOLDER  = os.path.abspath("recordings")
TRANSCRIPTS_FOLDER = os.path.abspath("transcripts")
SUMMARIZE_FOLDER   = os.path.abspath("summarize")

for folder in (RECORDINGS_FOLDER, TRANSCRIPTS_FOLDER, SUMMARIZE_FOLDER):
    os.makedirs(folder, exist_ok=True)

if not GEMINI_API_KEY:
    print("[ERROR] GEMINI_API_KEY is not set in .env — summarization will be skipped.")
else:
    genai.configure(api_key=GEMINI_API_KEY)

# ---------------------------------------------------------------------------
# Load Whisper model once at startup
# ---------------------------------------------------------------------------
print("[Watchdog] Loading Whisper model — this may take a moment...")
import whisper
model = whisper.load_model("turbo")
print("[Watchdog] Whisper ready.\n")

# ---------------------------------------------------------------------------
# Event handler
# ---------------------------------------------------------------------------
class FileHandler(FileSystemEventHandler):

    def on_created(self, event):
        if event.is_directory:
            return

        abs_path = os.path.abspath(event.src_path)

        if abs_path.endswith(".wav"):
            time.sleep(2)  # wait for server to finish writing
            print(f"[Watchdog] New audio detected: {abs_path}")
            self._transcribe(abs_path)

        elif abs_path.endswith(".txt") and abs_path.startswith(TRANSCRIPTS_FOLDER):
            time.sleep(1)
            print(f"[Watchdog] New transcript detected: {abs_path}")
            self._summarize(abs_path)

    # -----------------------------------------------------------------------

    def _transcribe(self, audio_path: str):
        """Transcribe a .wav file with Whisper and save to transcripts/."""
        try:
            base     = os.path.splitext(os.path.basename(audio_path))[0]
            out_path = os.path.join(TRANSCRIPTS_FOLDER, f"{base}.txt")

            if os.path.exists(out_path):
                print(f"[Transcriber] Already exists, skipping: {out_path}")
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
        """Summarize a transcript using Gemini API and save to summarize/."""
        if not GEMINI_API_KEY:
            print("[Summarizer] Skipping — GEMINI_API_KEY not set.")
            return

        try:
            base     = os.path.splitext(os.path.basename(input_path))[0]
            out_path = os.path.join(SUMMARIZE_FOLDER, f"{base}.txt")

            if os.path.exists(out_path):
                print(f"[Summarizer] Already exists, skipping: {out_path}")
                return

            with open(input_path, "r", encoding="utf-8") as f:
                transcript = f.read().strip()

            if not transcript:
                print("[Summarizer] Transcript is empty — skipping.")
                return

            print(f"[Summarizer] Sending to Gemini: {input_path}")

            prompt = (
                "You are a note-taking assistant for university lectures.\n"
                "Summarize the following lecture transcript into clear, concise bullet points "
                "covering the key topics, concepts, and takeaways. "
                "Group related points under short headings where appropriate.\n\n"
                f"Transcript:\n{transcript}"
            )

            gemini_model = genai.GenerativeModel("gemini-2.5-flash")
            response     = gemini_model.generate_content(prompt)
            summary      = response.text.strip()

            if not summary:
                print("[Summarizer] Gemini returned empty response — skipping.")
                return

            with open(out_path, "w", encoding="utf-8") as f:
                f.write(summary)
            print(f"[Summarizer] Saved: {out_path}")

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

    print(f"[Watchdog] Monitoring:")
    print(f"  {RECORDINGS_FOLDER}")
    print(f"  {TRANSCRIPTS_FOLDER}")
    print("[Watchdog] Press Ctrl+C to stop.\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[Watchdog] Shutting down...")
        observer.stop()
    observer.join()
    print("[Watchdog] Stopped.")