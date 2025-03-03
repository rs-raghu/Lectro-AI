import wave
import numpy as np

filename = "D:/Hello World/Arduino/recordings/53cb1229_1.wav"  # Change to your file

with wave.open(filename, 'rb') as wf:
    audio_data = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16)

print("Min:", np.min(audio_data), "Max:", np.max(audio_data))

if np.all(audio_data == 0):
    print("Error: Audio is completely silent (only zeros recorded).")
else:
    print("Audio contains valid data.")
