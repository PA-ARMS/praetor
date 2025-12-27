import os
import sys

def add_espeak_to_path() -> None:
    possible_paths = [
        r"C:\Program Files\eSpeak NG",
        r"C:\Program Files (x86)\eSpeak NG",
    ]
    for p in possible_paths:
        if os.path.isdir(p):
            os.environ["PATH"] = os.environ.get("PATH", "") + os.pathsep + p

def main() -> int:
    add_espeak_to_path()
    try:
        from TTS.api import TTS
        print("IMPORT_TTS=OK")
    except Exception as e:
        print("IMPORT_TTS=ERR", repr(e))
        return 1
    try:
        import torch
        print("TORCH=OK", torch.__version__)
    except Exception as e:
        print("TORCH=ERR", repr(e))
        return 1
    try:
        print("LOADING=START")
        t = TTS(model_name="tts_models/en/vctk/vits", progress_bar=False)
        print("LOADING=DONE")
    except Exception as e:
        print("LOADING=ERR", repr(e))
        return 2
    return 0

if __name__ == "__main__":
    sys.exit(main())


