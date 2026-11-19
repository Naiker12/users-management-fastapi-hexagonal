from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx
from tenacity import Retrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from users_management.circuit_breaker import CircuitBreaker, CircuitOpenError

logger = logging.getLogger(__name__)


class BrevoDeliveryError(RuntimeError):
    pass


class BrevoTransientError(BrevoDeliveryError):
    pass


@dataclass(frozen=True)
class BrevoEmailRequest:
    sender_address: str
    sender_name: str
    recipient: str
    subject: str
    html_content: str

    def to_payload(self) -> dict:
        return {
            "sender": {"name": self.sender_name, "email": self.sender_address},
            "to": [{"email": self.recipient}],
            "subject": self.subject,
            "htmlContent": self.html_content,
        }


class BrevoEmailSender:
    def __init__(self, settings, client: httpx.Client | None = None,
                 circuit_breaker: CircuitBreaker | None = None):
        if not settings.brevo_api_key:
            raise ValueError("BREVO_API_KEY is required when EMAIL_PROVIDER=brevo")
        if not settings.brevo_from_address:
            raise ValueError("BREVO_FROM_ADDRESS is required when EMAIL_PROVIDER=brevo")
        self.settings = settings
        timeout = httpx.Timeout(settings.brevo_read_timeout,
                                 connect=settings.brevo_connect_timeout)
        self.client = client or httpx.Client(base_url=settings.brevo_base_url.rstrip("/"),
                                             timeout=timeout)
        self.breaker = circuit_breaker or CircuitBreaker(
            failure_threshold=settings.brevo_circuit_failure_threshold,
            window_size=settings.brevo_circuit_window_size,
            minimum_calls=settings.brevo_circuit_minimum_calls,
            open_duration=settings.brevo_circuit_open_duration,
        )
        self.retryer = Retrying(
            stop=stop_after_attempt(settings.brevo_retry_max_attempts),
            wait=wait_exponential(
                multiplier=settings.brevo_retry_initial_delay,
                exp_base=settings.brevo_retry_multiplier,
                min=settings.brevo_retry_initial_delay,
            ),
            retry=retry_if_exception_type(
                (httpx.TimeoutException, httpx.NetworkError, BrevoTransientError)
            ),
            reraise=True,
        )

    def send(self, to: str, subject: str, body: str) -> None:
        request = BrevoEmailRequest(
            sender_address=self.settings.brevo_from_address,
            sender_name=self.settings.brevo_from_name,
            recipient=to,
            subject=subject,
            html_content=body,
        )
        try:
            self.breaker.before_call()
            self.retryer(self._send_once, request.to_payload())
        except CircuitOpenError:
            raise
        except Exception as exc:
            self.breaker.record_failure()
            logger.warning("Brevo email delivery failed (%s)", type(exc).__name__)
            raise BrevoDeliveryError("Brevo could not deliver the email") from exc
        self.breaker.record_success()

    def _send_once(self, payload: dict) -> None:
        response = self.client.post(
            "/v3/smtp/email",
            headers={"api-key": self.settings.brevo_api_key,
                     "accept": "application/json", "content-type": "application/json"},
            json=payload,
        )
        if response.status_code == 429 or response.status_code >= 500:
            raise BrevoTransientError(f"Transient Brevo response: {response.status_code}")
        if response.is_error:
            raise BrevoDeliveryError(f"Brevo rejected the request: {response.status_code}")

    def close(self) -> None:
        self.client.close()
