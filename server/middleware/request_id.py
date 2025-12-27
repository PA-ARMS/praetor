"""
Request ID Middleware
Adds unique request ID to all requests for tracing
"""
import uuid
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from server.utils.logger import setup_logger

logger = setup_logger("request_id")


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Adds unique request ID to each request for tracing"""
    
    async def dispatch(self, request: Request, call_next):
        # Generate unique request ID
        request_id = str(uuid.uuid4())[:8]  # Short ID for readability
        
        # Store in request state for use in handlers
        request.state.request_id = request_id
        
        # Add to response headers
        response: Response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        
        return response









