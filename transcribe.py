import os
import whisper

# Set FFmpeg path manually
os.environ["PATH"] += os.pathsep + r"C:\ProgramData\chocolatey\bin"

# Load Whisper model
model = whisper.load_model("base")

# Transcribe audio
result = model.transcribe("D:/Hello World/Arduino/recordings/recording.wav")
print(result["text"])