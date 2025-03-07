import os
import subprocess
import sys

# Path to Ollama executable
OLLAMA_PATH = r"C:/Users/raghu/AppData/Local/Programs/Ollama/ollama.exe"  # Update if needed

# Folder to save summaries
SUMMARIZE_FOLDER = "summarize"

def summarize_text(input_file):
    """Summarizes a transcript file using the local Ollama Mistral model and saves the summary."""
    
    if not os.path.exists(input_file):
        print(f"[Error] File not found: {input_file}")
        return
    
    # Ensure summarize folder exists
    os.makedirs(SUMMARIZE_FOLDER, exist_ok=True)

    # Extract filename without extension
    base_filename = os.path.splitext(os.path.basename(input_file))[0]
    output_file = os.path.join(SUMMARIZE_FOLDER, f"{base_filename}.txt")

    # Read transcript
    with open(input_file, "r", encoding="utf-8") as f:
        transcript = f.read().strip()
    
    if not transcript:
        print("[Warning] Transcript is empty. Skipping summarization.")
        return

    print(f"[Summarizer] Summarizing: {input_file}")

    try:
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

# Check if the script is being run with arguments from watchdog
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("[Error] Usage: python summarize.py <input_txt_path>")
        sys.exit(1)
    
    input_txt_path = sys.argv[1]  # Get file path from watchdog
    summarize_text(input_txt_path)
