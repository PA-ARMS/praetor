"""
Text-to-Speech service using Coqui TTS
Provides high-quality, human-like voice synthesis
"""
import os
import tempfile
from pathlib import Path
from typing import Optional
import torch
import hashlib

try:
    from TTS.api import TTS
    COQUI_AVAILABLE = True
except ImportError:
    COQUI_AVAILABLE = False
    TTS = None

# Optional offline fallback: Windows SAPI via pyttsx3
try:
    import pyttsx3  # Offline TTS engine (SAPI5 on Windows)
    SAPI_AVAILABLE = True
except Exception:
    SAPI_AVAILABLE = False
    pyttsx3 = None

from server.config import settings
from server.utils.logger import setup_logger


class TTSService:
    """Text-to-Speech service using Coqui TTS"""
    
    def __init__(self):
        self.logger = setup_logger("tts")
        self.tts = None
        self.model_name = None
        self.voice_name = None
        self.initialized = False
        self.backend: str = "none"  # "coqui" | "sapi" | "none"
        self._sapi_engine = None
        
    def initialize(self, model_name: str = "tts_models/en/vctk/vits", voice_name: Optional[str] = None):
        """Initialize TTS with a specific model and voice"""
        # Try Coqui first if available
        if COQUI_AVAILABLE:
            try:
                # Ensure eSpeak NG is on PATH for phonemizer (Windows)
                try:
                    import platform
                    if platform.system().lower().startswith("win"):
                        es_candidates = [
                            r"C:\Program Files\eSpeak NG",
                            r"C:\Program Files (x86)\eSpeak NG",
                            r"C:\Program Files\eSpeak\command_line",
                            r"C:\Program Files (x86)\eSpeak\command_line",
                        ]
                        current_path = os.environ.get("PATH", "")
                        for p in es_candidates:
                            if os.path.isdir(p) and p not in current_path:
                                os.environ["PATH"] = current_path + os.pathsep + p
                                current_path = os.environ["PATH"]
                        # Explicitly set environment overrides used by phonemizers
                        exe_candidates = [
                            r"C:\Program Files\eSpeak NG\espeak-ng.exe",
                            r"C:\Program Files (x86)\eSpeak NG\espeak-ng.exe",
                            r"C:\Program Files\eSpeak\command_line\espeak.exe",
                            r"C:\Program Files (x86)\eSpeak\command_line\espeak.exe",
                        ]
                        lib_candidates = [
                            r"C:\Program Files\eSpeak NG\libespeak-ng.dll",
                            r"C:\Program Files (x86)\eSpeak NG\libespeak-ng.dll",
                            r"C:\Program Files\eSpeak\command_line\espeak.dll",
                            r"C:\Program Files (x86)\eSpeak\command_line\espeak.dll",
                        ]
                        for exe in exe_candidates:
                            if os.path.isfile(exe):
                                os.environ.setdefault("ESPEAK_PATH", exe)
                                os.environ.setdefault("ESPEAK", exe)
                                break
                        for lib in lib_candidates:
                            if os.path.isfile(lib):
                                # Common env var used by phonemizer/espeak wrappers
                                os.environ.setdefault("PHONEMIZER_ESPEAK_LIBRARY", lib)
                                os.environ.setdefault("ESPEAK_LIBRARY", lib)
                                os.environ.setdefault("ESPEAK_NG_LIBRARY", lib)
                                break
                except Exception:
                    pass
                device = "cuda" if torch.cuda.is_available() else "cpu"
                self.logger.info(f"Initializing Coqui TTS on device: {device}")
                self.tts = TTS(model_name=model_name, progress_bar=False)
                self.model_name = model_name
                self.voice_name = voice_name
                self.tts.to(device)
                self.backend = "coqui"
                self.initialized = True
                self.logger.info(f"Coqui TTS initialized successfully with model: {model_name}")
                if "vctk" in model_name.lower():
                    try:
                        voices = self.tts.speakers if hasattr(self.tts, 'speakers') else []
                        if voices and not voice_name:
                            self.voice_name = voices[0] if isinstance(voices, list) else list(voices)[0]
                            self.logger.debug(f"Using default voice: {self.voice_name}")
                    except Exception as e:
                        self.logger.warning(f"Could not list voices: {e}")
                return
            except Exception as e:
                self.logger.warning(f"Error initializing Coqui TTS: {e}")
                # Fallback to SAPI if available
        
        if SAPI_AVAILABLE:
            try:
                self.logger.info("Initializing pyttsx3 (Windows SAPI) TTS fallback")
                self._sapi_engine = pyttsx3.init()
                # Select voice if provided
                if voice_name:
                    try:
                        for v in self._sapi_engine.getProperty('voices'):
                            if voice_name.lower() in (v.name or '').lower():
                                self._sapi_engine.setProperty('voice', v.id)
                                self.voice_name = v.name
                                break
                    except Exception:
                        pass
                self.model_name = "sapi5"
                self.backend = "sapi"
                self.initialized = True
                self.logger.info("pyttsx3 TTS initialized successfully (SAPI)")
                return
            except Exception as e:
                self.logger.warning(f"Error initializing pyttsx3 TTS: {e}")
        
        raise RuntimeError("No TTS backend available. Install coqui-tts or pyttsx3.")
    
    def synthesize(self, text: str, output_path: Optional[str] = None, voice_name: Optional[str] = None) -> str:
        """
        Convert text to speech
        
        Args:
            text: Text to convert to speech
            output_path: Optional path to save audio file
            voice_name: Optional voice name (for multi-voice models)
        
        Returns:
            Path to generated audio file
        """
        if not self.initialized:
            raise RuntimeError("TTS service not initialized. Call initialize() first.")
        
        # Use provided voice or default
        voice = voice_name or self.voice_name
        
        # Create temporary file if no output path provided
        if not output_path:
            temp_dir = Path(settings.DATA_DIR) / "audio"
            temp_dir.mkdir(exist_ok=True)
            # Use hash of text for filename (same text = same file, can be cached)
            import hashlib
            text_hash = hashlib.md5(text.encode()).hexdigest()[:12]
            output_path = str(temp_dir / f"tts_{text_hash}.wav")
        
        # Check if file already exists (cache)
        if os.path.exists(output_path):
            return output_path
        
        try:
            if self.backend == "coqui":
                # Synthesize speech with Coqui
                if voice and hasattr(self.tts, 'speakers') and getattr(self.tts, 'speakers', None):
                    try:
                        self.tts.tts_to_file(text=text, file_path=output_path, speaker=voice)
                    except Exception as e:
                        print(f"Warning: Voice {voice} failed, using default: {e}")
                        self.tts.tts_to_file(text=text, file_path=output_path)
                else:
                    self.tts.tts_to_file(text=text, file_path=output_path)
            elif self.backend == "sapi":
                # Synthesize speech with pyttsx3 (SAPI)
                engine = self._sapi_engine or pyttsx3.init()
                if voice:
                    try:
                        for v in engine.getProperty('voices'):
                            if voice.lower() in (v.name or '').lower():
                                engine.setProperty('voice', v.id)
                                break
                    except Exception:
                        pass
                engine.save_to_file(text, output_path)
                engine.runAndWait()
            else:
                raise RuntimeError("No TTS backend initialized")
            
            return output_path
            
        except Exception as e:
            self.logger.error(f"Error synthesizing speech: {e}", exc_info=True)
            raise
    
    def get_available_voices(self) -> list:
        """Get list of available voices for current model"""
        if not self.initialized:
            return []
        
        try:
            if self.backend == "coqui" and self.tts and hasattr(self.tts, 'speakers'):
                speakers = self.tts.speakers
                if isinstance(speakers, list):
                    return speakers
                elif isinstance(speakers, dict):
                    return list(speakers.keys())
                return []
            if self.backend == "sapi" and self._sapi_engine:
                try:
                    return [v.name for v in self._sapi_engine.getProperty('voices') if getattr(v, 'name', None)]
                except Exception:
                    return []
            return []
        except Exception:
            return []
    
    def is_available(self) -> bool:
        """Check if TTS is available"""
        return self.initialized and (self.backend in ("coqui", "sapi"))


# Global TTS service instance
tts_service = TTSService()

# Initialize on import (lazy loading)
_initialization_attempted = False

def get_tts_service():
    """Get or initialize TTS service"""
    global _initialization_attempted
    
    if not tts_service.initialized and not _initialization_attempted:
        _initialization_attempted = True
        try:
            # Use high-quality VCTK model with multiple voices
            logger = setup_logger("tts")
            logger.info("Initializing Coqui TTS service...")
            tts_service.initialize(
                model_name="tts_models/en/vctk/vits",
                voice_name=None  # Will use default
            )
            logger.info("Coqui TTS service initialized successfully.")
        except Exception as e:
            logger = setup_logger("tts")
            logger.warning(f"Could not initialize TTS service: {e}")
            logger.warning("TTS features will be disabled.")
    
    return tts_service

