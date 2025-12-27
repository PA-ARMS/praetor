"""
Text-to-Speech API routes
"""
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
import os

from server.utils.logger import setup_logger

try:
    from server.services.tts_service import get_tts_service
    TTS_AVAILABLE = True
except ImportError as e:
    logger = setup_logger("tts")
    logger.warning(f"TTS service not available: {e}")
    TTS_AVAILABLE = False
    get_tts_service = None

from server.middleware.auth_middleware import require_auth
from server.models import User

router = APIRouter()
if TTS_AVAILABLE:
    logger = setup_logger("tts")


class TTSRequest(BaseModel):
    text: str
    voice: Optional[str] = None


class TTSResponse(BaseModel):
    audio_url: str
    voice_used: str
    text_length: int


@router.post("/speak", response_class=FileResponse)
async def text_to_speech(
    request: TTSRequest,
    current_user: User = Depends(require_auth)
):
    """Convert text to speech and return audio file"""
    if not TTS_AVAILABLE or not get_tts_service:
        raise HTTPException(
            status_code=503,
            detail="TTS service is not available. Please install Coqui TTS: pip install coqui-tts torch"
        )
    
    try:
        tts = get_tts_service()
        
        if not tts.is_available():
            raise HTTPException(
                status_code=503,
                detail="TTS service is not available. Please check installation."
            )
        
        if not request.text.strip():
            raise HTTPException(
                status_code=400,
                detail="Text cannot be empty"
            )
        
        # Clean text - remove markdown, citations, etc. for better speech
        import re
        text = request.text
        
        # Remove markdown links [text](url)
        text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
        # Remove markdown formatting
        text = re.sub(r'\*\*([^\*]+)\*\*', r'\1', text)  # Bold
        text = re.sub(r'\*([^\*]+)\*', r'\1', text)  # Italic
        # Remove code blocks
        text = re.sub(r'```[^`]+```', '', text)
        text = re.sub(r'`([^`]+)`', r'\1', text)
        # Remove URLs
        text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)
        # Clean up multiple spaces
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        # Limit text length for performance
        max_length = 5000
        if len(text) > max_length:
            text = text[:max_length] + "... [text truncated]"
        
        # Synthesize speech
        audio_path = tts.synthesize(
            text=text,
            voice_name=request.voice
        )
        
        # Get voice name used
        voice_used = request.voice or tts.voice_name or "default"
        
        if not os.path.exists(audio_path):
            raise HTTPException(
                status_code=500,
                detail="Audio file was not generated"
            )
        
        # Return audio file
        return FileResponse(
            path=audio_path,
            media_type="audio/wav",
            filename="speech.wav",
            headers={
                "X-Voice-Used": voice_used,
                "X-Text-Length": str(len(text))
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error generating speech: {str(e)}"
        )


@router.get("/voices")
async def list_voices(
    current_user: User = Depends(require_auth)
):
    """Get list of available voices"""
    if not TTS_AVAILABLE or not get_tts_service:
        return {
            "available": False,
            "voices": [],
            "message": "TTS service is not available. Please install Coqui TTS."
        }
    
    try:
        tts = get_tts_service()
        
        if not tts.is_available():
            return {
                "available": False,
                "voices": [],
                "message": "TTS service is not available"
            }
        
        voices = tts.get_available_voices()
        
        return {
            "available": True,
            "voices": voices,
            "current_voice": tts.voice_name or "default",
            "model": tts.model_name
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error listing voices: {str(e)}"
        )


@router.get("/status")
async def tts_status():
    """Get TTS service status"""
    if not TTS_AVAILABLE or not get_tts_service:
        return {
            "enabled": False,
            "error": "TTS service not available. Please install Coqui TTS: pip install coqui-tts torch"
        }
    
    try:
        tts = get_tts_service()
        
        return {
            "enabled": tts.is_available(),
            "model": tts.model_name if tts.initialized else None,
            "voice": tts.voice_name if tts.initialized else None,
            "device": "cuda" if tts.is_available() and hasattr(tts.tts, 'device') else "cpu"
        }
    
    except Exception as e:
        return {
            "enabled": False,
            "error": str(e)
        }

