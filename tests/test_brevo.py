import threading

import httpx
import pytest

from users_management.application import EmailNotificationService
from users_management.async_email_sender import AsyncEmailSender, EmailQueueFullError
from users_management.brevo_email_sender import (
    BrevoDeliveryError,
    BrevoEmailRequest,
    BrevoEmailSender,
)
from users_management.circuit_breaker import CircuitBreaker, CircuitOpenError
from users_management.config import Settings
from users_management.domain import User, UserRole, UserStatus


class CaptureSender:
    def __init__(self):
        self.messages = []

    def send(self, *args):
        self.messages.append(args)


def brevo_settings(**kwargs):
    return Settings(brevo_api_key="test-key", brevo_from_address="sender@example.com",
                    brevo_from_name="Test sender", brevo_retry_initial_delay=0,
                    brevo_retry_multiplier=1, **kwargs)


def test_brevo_request_has_expected_payload():
    request = BrevoEmailRequest("from@example.com", "Sender", "to@example.com", "Hello", "<p>Hi</p>")
    assert request.to_payload() == {
        "sender": {"name": "Sender", "email": "from@example.com"},
        "to": [{"email": "to@example.com"}],
        "subject": "Hello",
        "htmlContent": "<p>Hi</p>",
    }


def test_brevo_sender_posts_with_api_key_and_payload():
    seen = {}

    def handler(request):
        seen["path"] = request.url.path
        seen["key"] = request.headers["api-key"]
        seen["payload"] = request.read().decode()
        return httpx.Response(201, json={"messageId": "ok"})

    client = httpx.Client(transport=httpx.MockTransport(handler), base_url="https://api.brevo.com")
    BrevoEmailSender(brevo_settings(), client=client).send("to@example.com", "Hi", "<p>Hello</p>")
    assert seen["path"] == "/v3/smtp/email"
    assert seen["key"] == "test-key"
    assert '"htmlContent":"<p>Hello</p>"' in seen["payload"]
    client.close()


def test_brevo_sender_retries_transient_errors_then_succeeds():
    attempts = 0

    def handler(_request):
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            return httpx.Response(503)
        return httpx.Response(201)

    client = httpx.Client(transport=httpx.MockTransport(handler), base_url="https://api.brevo.com")
    BrevoEmailSender(brevo_settings(), client=client).send("to@example.com", "Hi", "body")
    assert attempts == 3
    client.close()


def test_brevo_sender_does_not_retry_permanent_4xx():
    attempts = 0

    def handler(_request):
        nonlocal attempts
        attempts += 1
        return httpx.Response(400)

    client = httpx.Client(transport=httpx.MockTransport(handler), base_url="https://api.brevo.com")
    with pytest.raises(BrevoDeliveryError):
        BrevoEmailSender(brevo_settings(), client=client).send("to@example.com", "Hi", "body")
    assert attempts == 1
    client.close()


def test_brevo_sender_requires_api_key_and_from_address():
    with pytest.raises(ValueError, match="BREVO_API_KEY"):
        BrevoEmailSender(Settings(brevo_from_address="sender@example.com"))
    with pytest.raises(ValueError, match="BREVO_FROM_ADDRESS"):
        BrevoEmailSender(Settings(brevo_api_key="test-key"))


def test_circuit_breaker_opens_then_allows_call_after_timeout():
    now = [0.0]
    breaker = CircuitBreaker(failure_threshold=50, window_size=4, minimum_calls=2,
                             open_duration=5, clock=lambda: now[0])
    breaker.record_failure()
    breaker.record_success()
    with pytest.raises(CircuitOpenError):
        breaker.before_call()
    now[0] = 6
    breaker.before_call()
    assert not breaker.results


def test_circuit_breaker_validates_configuration():
    with pytest.raises(ValueError):
        CircuitBreaker(failure_threshold=0)
    with pytest.raises(ValueError):
        CircuitBreaker(window_size=2, minimum_calls=3)


def test_async_sender_uses_worker_thread_and_bounds_queue():
    entered, release = threading.Event(), threading.Event()

    class BlockingSender:
        def send(self, *_):
            entered.set()
            release.wait(timeout=3)

    sender = AsyncEmailSender(BlockingSender(), max_workers=1, max_queue_size=1)
    first = sender.send("a@example.com", "one", "body")
    assert entered.wait(timeout=2)
    second = sender.send("b@example.com", "two", "body")
    with pytest.raises(EmailQueueFullError):
        sender.send("c@example.com", "three", "body")
    release.set()
    first.result(timeout=3)
    second.result(timeout=3)
    sender.shutdown()


def test_notification_service_renders_and_escapes_template_values():
    user = User(name="<Ana>", email="ana@example.com", password_hash="hash",
                role=UserRole.MEMBER, status=UserStatus.PENDING)
    sender = CaptureSender()
    notifications = EmailNotificationService(sender)
    notifications.user_created(user, "secret&temporary")
    to, subject, body = sender.messages[0]
    assert to == "ana@example.com"
    assert subject == "Usuario creado"
    assert "&lt;Ana&gt;" in body
    assert "secret&amp;temporary" in body
    notifications.user_updated(user)
    assert sender.messages[1][1] == "Usuario actualizado"
