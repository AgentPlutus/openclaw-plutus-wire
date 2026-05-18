"""Runtime status classification for stable cron execution."""

from __future__ import annotations

from dataclasses import dataclass


OK = "ok"
NETWORK_UNAVAILABLE = "network_unavailable"
AUTH_REQUIRED = "auth_required"
CAPTCHA_OR_CHALLENGE = "captcha_or_challenge"
RATE_LIMITED = "rate_limited"
ADAPTER_ERROR = "adapter_error"
SKIPPED_BACKOFF = "skipped_backoff"

RECOVERABLE_STATES = {
    NETWORK_UNAVAILABLE,
    AUTH_REQUIRED,
    CAPTCHA_OR_CHALLENGE,
    RATE_LIMITED,
    ADAPTER_ERROR,
    SKIPPED_BACKOFF,
}


@dataclass(frozen=True)
class RuntimeClassification:
    status: str
    reason: str = ""

    @property
    def ok(self) -> bool:
        return self.status == OK


def classify_failure(message: str = "", *, returncode: int | None = None) -> RuntimeClassification:
    text = (message or "").lower()
    if returncode == 0 and not text:
        return RuntimeClassification(OK, "")
    if any(token in text for token in ("no ct0", "authrequired", "401", "403", "login", "logged out")):
        return RuntimeClassification(AUTH_REQUIRED, "browser session is not authenticated")
    if any(token in text for token in ("captcha", "arkose", "challenge")):
        return RuntimeClassification(CAPTCHA_OR_CHALLENGE, "browser session needs challenge resolution")
    if any(token in text for token in ("429", "rate limit", "rate-limited", "too many requests")):
        return RuntimeClassification(RATE_LIMITED, "source is rate limited")
    if any(
        token in text
        for token in (
            "network",
            "timed out",
            "timeout",
            "etimedout",
            "enotfound",
            "econnreset",
            "econnrefused",
            "fetch failed",
            "no route",
            "err_internet_disconnected",
            "proxy",
        )
    ):
        return RuntimeClassification(NETWORK_UNAVAILABLE, "network path unavailable")
    return RuntimeClassification(ADAPTER_ERROR, "adapter command failed")


def classify_health(payload: dict | None, *, returncode: int, stderr: str = "") -> RuntimeClassification:
    if returncode != 0:
        return classify_failure(stderr, returncode=returncode)
    payload = payload or {}
    if not payload.get("x_logged_in"):
        return RuntimeClassification(AUTH_REQUIRED, "x_logged_in=false")
    if payload.get("x_captcha_detected"):
        return RuntimeClassification(CAPTCHA_OR_CHALLENGE, "x_captcha_detected=true")
    if payload.get("x_rate_limited"):
        return RuntimeClassification(RATE_LIMITED, "x_rate_limited=true")
    return RuntimeClassification(OK, "health preflight passed")

