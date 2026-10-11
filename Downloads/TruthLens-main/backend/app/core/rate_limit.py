import redis
from fastapi import HTTPException, status, Request
from typing import Optional
from app.core.config import settings
import time

try:
    redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
except Exception:
    redis_client = None

class RateLimiter:
    def __init__(self, requests: int, window: int):
        self.requests = requests
        self.window = window
        self._local_history = {}

    def __call__(self, request: Request):
        # Use client IP as the identifier
        client_ip = request.client.host if request.client else "127.0.0.1"
        endpoint = request.url.path
        key = f"rate_limit:{endpoint}:{client_ip}"
        
        current_time = int(time.time())
        window_start = current_time - self.window
        
        # Try Redis first
        try:
            if redis_client is not None:
                # Clean up old requests outside the window
                redis_client.zremrangebyscore(key, 0, window_start)
                
                # Count requests in current window
                request_count = redis_client.zcard(key)
                
                if request_count >= self.requests:
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail="Too many requests, please try again later."
                    )
                    
                # Add current request
                redis_client.zadd(key, {str(current_time): current_time})
                # Set expiry on the key to avoid Redis filling up
                redis_client.expire(key, self.window)
                return
        except HTTPException:
            raise
        except Exception:
            # Fallback to local in-memory rate limiting when Redis is not available
            pass
        
        # Local in-memory sliding window fallback
        timestamps = self._local_history.get(key, [])
        timestamps = [t for t in timestamps if t > window_start]
        if len(timestamps) >= self.requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests, please try again later."
            )
        timestamps.append(current_time)
        self._local_history[key] = timestamps

# Parse settings (e.g. "5/minute" -> requests=5, window=60)
def parse_rate_limit(limit_str: str) -> RateLimiter:
    try:
        req_str, period_str = limit_str.split("/")
        requests = int(req_str)
        if period_str == "minute":
            window = 60
        elif period_str == "hour":
            window = 3600
        else:
            window = 60
        return RateLimiter(requests, window)
    except Exception:
        return RateLimiter(5, 60) # fallback

login_rate_limiter = parse_rate_limit(settings.AUTH_LOGIN_RATE_LIMIT)
register_rate_limiter = parse_rate_limit(settings.AUTH_REGISTER_RATE_LIMIT)
