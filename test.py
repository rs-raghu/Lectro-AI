import whisper
import os
import sys

# Load Whisper model
model = whisper.load_model("turbo")

def transcribe_audio(audio_path):
    """Transcribes an audio file using Whisper and saves the transcript with the same name."""
    
    if not os.path.exists(audio_path):
        print(f"[Error] File not found: {audio_path}")
        return
    
    print(f"[Transcriber] Processing file: {audio_path}")

    try:
        # Extract filename (without extension) to match output
        base_filename = os.path.splitext(os.path.basename(audio_path))[0]

        # Transcribe audio (forcing Whisper to process full audio without context bias)
        result = model.transcribe(audio_path, condition_on_previous_text=False)

        transcript = result["text"].strip()
        if not transcript:
            print("[Warning] No transcription generated.")
            return

        # Save transcript in the same folder as the audio file
        transcript_filename = os.path.join(os.path.dirname(audio_path), f"{base_filename}.txt")

        with open(transcript_filename, "w", encoding="utf-8") as f:
            f.write(transcript)

        print(f"[Transcriber] Transcript saved: {transcript_filename}")

    except Exception as e:
        print(f"[Error] Transcription failed: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("[Error] Usage: python test.py <audio_path>")
        sys.exit(1)

    audio_path = sys.argv[1]
    transcribe_audio(audio_path)
