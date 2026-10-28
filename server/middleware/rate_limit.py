"""
Rate Limiting Middleware
Prevents abuse by limiting requests per IP address
"""
import time
from collections import defaultdict
from typing import Dict, Tuple
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from server.utils.logger import setup_logger

logger = setup_logger("rate_limit")


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware
    
    Limits:
    - Chat queries: 30 per minute per IP
    - Auth endpoints: 10 per minute per IP
    - Other endpoints: 60 per minute per IP
    """
    
    def __init__(self, app):
        super().__init__(app)
        # Store request timestamps per IP
        self.request_history: Dict[str, list] = defaultdict(list)
        # Rate limits (requests per minute)
        self.limits = {
            "/api/chat/query": 30,
            "/api/chat/stream": 30,
            "/api/auth/login": 10,
            "/api/auth/register": 5,
            "default": 60
        }
        # Cleanup old entries every 5 minutes
        self.last_cleanup = time.time()
        self.cleanup_interval = 300  # 5 minutes
    
    def get_rate_limit(self, path: str) -> int:
        """Get rate limit for a specific path"""
        for limit_path, limit in self.limits.items():
            if path.startswith(limit_path):
                return limit
        return self.limits["default"]
    
    def cleanup_old_entries(self):
        """Remove old entries to prevent memory growth"""
        current_time = time.time()
        if current_time - self.last_cleanup < self.cleanup_interval:
            return
        
        cutoff_time = current_time - 60  # Keep last minute
        for ip in list(self.request_history.keys()):
            self.request_history[ip] = [
                ts for ts in self.request_history[ip] if ts > cutoff_time
            ]
            if not self.request_history[ip]:
                del self.request_history[ip]
        
        self.last_cleanup = current_time
    
    def get_client_ip(self, request: Request) -> str:
        """Extract client IP address"""
        # Check for forwarded IP (if behind proxy)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        # Check for real IP
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        # Fallback to direct client
        if request.client:
            return request.client.host
        return "unknown"
    
    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health / liveness checks
        if request.url.path in ("/health", "/ping", "/api/ping", "/api/health"):
            return await call_next(request)
        
        # Cleanup old entries periodically
        self.cleanup_old_entries()
        
        # Get client IP and path
        client_ip = self.get_client_ip(request)
        path = request.url.path
        
        # Get rate limit for this path
        limit = self.get_rate_limit(path)
        
        # Check current request count
        current_time = time.time()
        window_start = current_time - 60  # Last 60 seconds
        
        # Filter requests in current window
        self.request_history[client_ip] = [
            ts for ts in self.request_history[client_ip] if ts > window_start
        ]
        
        # Check if limit exceeded
        if len(self.request_history[client_ip]) >= limit:
            logger.warning(f"Rate limit exceeded for {client_ip} on {path} ({limit}/min)")
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": True,
                    "message": f"Rate limit exceeded. Maximum {limit} requests per minute.",
                    "status_code": 429,
                    "retry_after": 60
                },
                headers={"Retry-After": "60"}
            )
        
        # Record this request
        self.request_history[client_ip].append(current_time)
        
        # Process request
        response = await call_next(request)
        return response

