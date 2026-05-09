"""Alert delivery for email, Telegram, and Discord."""

from __future__ import annotations

import smtplib
from email.message import EmailMessage

import requests

from .config import AlertConfig
from .logging_utils import get_logger
from .signals import Signal


def format_alert(signals: list[Signal]) -> str:
    """Create a plain-English alert message from ranked signals."""

    if not signals:
        return "No market-scanner signals met the configured threshold."
    lines = ["Market Scanner Paper-Trade Alerts", "", "Paper trading / alert-only. Not financial advice.", ""]
    for signal in signals:
        lines.extend(
            [
                f"{signal.symbol} | Score {signal.score}/100 | Confidence {signal.confidence:.0%}",
                signal.trade_idea,
                "",
            ]
        )
    return "\n".join(lines).strip()


class AlertManager:
    """Send alerts through configured channels; all channels are optional."""

    def __init__(self, config: AlertConfig) -> None:
        self.config = config
        self.logger = get_logger()

    def send(self, signals: list[Signal]) -> list[str]:
        """Send alerts and return channel result messages.

        Alert failures are logged per channel so one broken destination does not
        prevent the scan from completing or the signal log from being retained.
        """

        message = format_alert(signals)
        results: list[str] = []
        failures: list[str] = []
        if self.config.email_enabled:
            self._try_channel("email", self._send_email, message, results, failures)
        if self.config.telegram_enabled:
            self._try_channel("telegram", self._send_telegram, message, results, failures)
        if self.config.discord_enabled:
            self._try_channel("discord", self._send_discord, message, results, failures)
        if not results and not failures:
            results.append("alerts disabled; message printed locally")
            self.logger.info("Alerts disabled; printing alert locally")
            print(message)
        return results + failures

    def _try_channel(self, name: str, sender, message: str, results: list[str], failures: list[str]) -> None:
        try:
            sender(message)
            results.append(f"{name} sent")
        except Exception as exc:  # noqa: BLE001 - alert failures should not stop scans
            self.logger.exception("%s alert failed", name)
            failures.append(f"{name} failed: {exc}")

    def _send_email(self, message: str) -> None:
        required = [self.config.smtp_host, self.config.email_from, self.config.email_to]
        if not all(required):
            raise ValueError("Email alerts require SMTP_HOST, EMAIL_FROM, and EMAIL_TO")
        email = EmailMessage()
        email["Subject"] = "Market Scanner Paper-Trade Alert"
        email["From"] = self.config.email_from
        email["To"] = self.config.email_to
        email.set_content(message)
        with smtplib.SMTP(self.config.smtp_host, self.config.smtp_port, timeout=20) as smtp:
            smtp.starttls()
            if self.config.smtp_username and self.config.smtp_password:
                smtp.login(self.config.smtp_username, self.config.smtp_password)
            smtp.send_message(email)

    def _send_telegram(self, message: str) -> None:
        if not self.config.telegram_bot_token or not self.config.telegram_chat_id:
            raise ValueError("Telegram alerts require TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID")
        url = f"https://api.telegram.org/bot{self.config.telegram_bot_token}/sendMessage"
        response = requests.post(url, json={"chat_id": self.config.telegram_chat_id, "text": message}, timeout=20)
        response.raise_for_status()

    def _send_discord(self, message: str) -> None:
        if not self.config.discord_webhook_url:
            raise ValueError("Discord alerts require DISCORD_WEBHOOK_URL")
        response = requests.post(self.config.discord_webhook_url, json={"content": message[:1900]}, timeout=20)
        response.raise_for_status()
