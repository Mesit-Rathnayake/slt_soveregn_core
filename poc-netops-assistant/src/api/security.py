import base64
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from collections import defaultdict, deque


class SovereignTokenManager:
    """
    Zero-dependency HMAC-SHA256 signed bearer token manager (JWT-compatible compact format).
    Binds verified role, account/connection number, and service segment so callers cannot
    spoof X-User-Role headers or access another subscriber's account (IDOR protection).
    """

    def __init__(self, secret_key: str | None = None, ttl_seconds: int = 3600):
        env_secret = os.getenv("SLT_SESSION_SECRET", "").strip()
        self._secret = (secret_key or env_secret or secrets.token_urlsafe(32)).encode("utf-8")
        self.ttl_seconds = ttl_seconds

    @staticmethod
    def _b64url_encode(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")

    @staticmethod
    def _b64url_decode(segment: str) -> bytes:
        padding = "=" * (-len(segment) % 4)
        return base64.urlsafe_b64decode((segment + padding).encode("ascii"))

    def issue_token(
        self,
        *,
        role: str,
        subject: str,
        service_segment: str = "Fibre",
        display_name: str = "",
        ttl_seconds: int | None = None,
    ) -> str:
        now = int(time.time())
        header = {"alg": "HS256", "typ": "JWT"}
        payload = {
            "sub": subject,
            "role": role,
            "seg": service_segment,
            "name": display_name,
            "iat": now,
            "exp": now + (ttl_seconds or self.ttl_seconds),
            "jti": secrets.token_hex(8),
        }
        h_b64 = self._b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
        p_b64 = self._b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
        signing_input = f"{h_b64}.{p_b64}".encode("ascii")
        sig = hmac.new(self._secret, signing_input, hashlib.sha256).digest()
        return f"{h_b64}.{p_b64}.{self._b64url_encode(sig)}"

    def verify_token(self, token: str) -> dict | None:
        if not token or token.count(".") != 2:
            return None
        try:
            h_b64, p_b64, s_b64 = token.split(".", 2)
            signing_input = f"{h_b64}.{p_b64}".encode("ascii")
            expected_sig = hmac.new(self._secret, signing_input, hashlib.sha256).digest()
            actual_sig = self._b64url_decode(s_b64)
            if not hmac.compare_digest(expected_sig, actual_sig):
                return None
            payload = json.loads(self._b64url_decode(p_b64).decode("utf-8"))
            if int(payload.get("exp", 0)) < int(time.time()):
                return None
            return payload
        except Exception:
            return None


class SlidingWindowRateLimiter:
    """
    Thread-safe in-memory sliding-window rate limiter for API protection against
    OTP SMS pumping, brute-force attacks, and LLM quota exhaustion.
    In multi-instance cloud deployments, back this with AWS WAFv2 + Redis/ElastiCache.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._buckets: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str, max_requests: int, window_seconds: int) -> tuple[bool, int]:
        now = time.time()
        cutoff = now - window_seconds
        with self._lock:
            q = self._buckets[key]
            while q and q[0] <= cutoff:
                q.popleft()
            if len(q) >= max_requests:
                retry_after = max(1, int(q[0] + window_seconds - now))
                return False, retry_after
            q.append(now)
            return True, 0

    def reset(self):
        with self._lock:
            self._buckets.clear()
