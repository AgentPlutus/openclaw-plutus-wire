from lib.runtime_status import (
    AUTH_REQUIRED,
    CAPTCHA_OR_CHALLENGE,
    NETWORK_UNAVAILABLE,
    OK,
    RATE_LIMITED,
    classify_failure,
    classify_health,
)


def test_classify_failure_network():
    result = classify_failure("fetch failed: ETIMEDOUT")
    assert result.status == NETWORK_UNAVAILABLE


def test_classify_failure_auth():
    result = classify_failure("AuthRequiredError no ct0 cookie")
    assert result.status == AUTH_REQUIRED


def test_classify_failure_rate_limit():
    result = classify_failure("HTTP 429 rate-limited")
    assert result.status == RATE_LIMITED


def test_classify_health_ok():
    result = classify_health({"x_logged_in": True}, returncode=0)
    assert result.status == OK


def test_classify_health_captcha():
    result = classify_health({"x_logged_in": True, "x_captcha_detected": True}, returncode=0)
    assert result.status == CAPTCHA_OR_CHALLENGE
