import sys

try:
    from TTS.api import TTS
except Exception as e:
    print("COQUI_IMPORT_ERROR:", e)
    sys.exit(1)

model = "tts_models/en/vctk/vits"
print("Loading Coqui model:", model, flush=True)
try:
    t = TTS(model_name=model, progress_bar=False)
    print("MODEL_LOADED_OK", flush=True)
except Exception as e:
    print("MODEL_LOAD_ERROR:", e, flush=True)
    sys.exit(2)

