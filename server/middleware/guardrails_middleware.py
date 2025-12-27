"""
Guardrails middleware - Enforces AI Laws
Validates prompts and responses against the AI Laws code
"""
import json
import re
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from pathlib import Path
from server.utils.logger import setup_logger


class GuardrailsMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.logger = setup_logger("guardrails_middleware")
        self.ai_laws_path = Path(__file__).parent.parent.parent / "config" / "ai_laws.json"
        
        # Load AI Laws with protection/verification
        from server.services.ai_laws_protection import ai_laws_protection
        self.ai_laws = ai_laws_protection.load_ai_laws()
        
        # If AI Laws are invalid, system cannot proceed
        if not self.ai_laws:
            self.logger.critical("CRITICAL: AI Laws are invalid or have been tampered with. System cannot operate.")
            raise RuntimeError(
                "AI Laws verification failed. The AI Laws are IMMUTABLE and cannot be modified. "
                "Please restore the original ai_laws.json file."
            )
    
    def _load_ai_laws(self):
        """
        Load AI laws from config - DEPRECATED
        Use ai_laws_protection.load_ai_laws() instead for verification
        """
        # This method is kept for backward compatibility but should not be used
        from server.services.ai_laws_protection import ai_laws_protection
        return ai_laws_protection.load_ai_laws() or {}
    
    async def dispatch(self, request: Request, call_next):
        # Skip guardrails for non-chat endpoints
        if not request.url.path.startswith("/api/chat"):
            return await call_next(request)
        
        # For chat endpoints, add AI laws context to request state
        request.state.ai_laws = self.ai_laws
        
        response = await call_next(request)
        return response

def guardrails_middleware(app):
    """Factory function for guardrails middleware"""
    return GuardrailsMiddleware(app)

