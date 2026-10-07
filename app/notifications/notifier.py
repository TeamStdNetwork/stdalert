import logging
from abc import ABC, abstractmethod
from pydantic import BaseModel
from datetime import datetime, timezone
import httpx
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)

class NotificationEvent(BaseModel):
    event_type: str
    repo_full_name: str
    title: str
    message: str
    severity: str
    url: str | None = None
    timestamp: datetime = datetime.now(timezone.utc)

class BaseNotifier(ABC):
    @abstractmethod
    async def send(self, event: NotificationEvent) -> bool:
        pass

class SlackNotifier(BaseNotifier):
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    async def send(self, event: NotificationEvent) -> bool:
        color_map = {
            "info": "#36a64f",     # green
            "warning": "#ffcc00",  # yellow
            "critical": "#ff0000"  # red
        }
        color = color_map.get(event.severity.lower(), "#36a64f")

        payload = {
            "attachments": [
                {
                    "color": color,
                    "title": event.title,
                    "title_link": event.url,
                    "text": event.message,
                    "fields": [
                        {"title": "Repository", "value": event.repo_full_name, "short": True},
                        {"title": "Event Type", "value": event.event_type, "short": True}
                    ],
                    "footer": "STD Alert",
                    "ts": int(event.timestamp.timestamp())
                }
            ]
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(self.webhook_url, json=payload)
                response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Failed to send Slack notification: {e}")
            return False

class DiscordNotifier(BaseNotifier):
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    async def send(self, event: NotificationEvent) -> bool:
        color_map = {
            "info": 3066993,       # green
            "warning": 16766720,   # yellow
            "critical": 16711680   # red
        }
        color = color_map.get(event.severity.lower(), 3066993)

        payload = {
            "embeds": [
                {
                    "title": event.title,
                    "description": event.message,
                    "url": event.url,
                    "color": color,
                    "fields": [
                        {"name": "Repository", "value": event.repo_full_name, "inline": True},
                        {"name": "Event Type", "value": event.event_type, "inline": True}
                    ],
                    "timestamp": event.timestamp.isoformat()
                }
            ]
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(self.webhook_url, json=payload)
                response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Failed to send Discord notification: {e}")
            return False

class EmailNotifier(BaseNotifier):
    def __init__(self, smtp_host: str, smtp_port: int, username: str, password: str, from_email: str, to_emails: list[str]):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.from_email = from_email
        self.to_emails = to_emails

    async def send(self, event: NotificationEvent) -> bool:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[{event.severity.upper()}] {event.title} - {event.repo_full_name}"
        msg["From"] = self.from_email
        msg["To"] = ", ".join(self.to_emails)

        html = f"""
        <html>
          <body>
            <h2>{event.title}</h2>
            <p><strong>Repository:</strong> {event.repo_full_name}</p>
            <p><strong>Event:</strong> {event.event_type}</p>
            <p><strong>Severity:</strong> {event.severity}</p>
            <p>{event.message}</p>
            {f'<p><a href="{event.url}">View Details</a></p>' if event.url else ''}
          </body>
        </html>
        """
        
        part = MIMEText(html, "html")
        msg.attach(part)

        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.username, self.password)
                server.sendmail(self.from_email, self.to_emails, msg.as_string())
            return True
        except Exception as e:
            logger.error(f"Failed to send Email notification: {e}")
            return False

class NotificationManager:
    def __init__(self):
        self.channels: list[BaseNotifier] = []

    def add_channel(self, notifier: BaseNotifier):
        self.channels.append(notifier)

    async def notify(self, event: NotificationEvent):
        for channel in self.channels:
            await channel.send(event)

    async def notify_scan_complete(self, repo_full_name: str, scan_result: dict, url: str | None = None):
        event = NotificationEvent(
            event_type="scan_complete",
            repo_full_name=repo_full_name,
            title="Dependency Scan Complete",
            message=f"Scan completed. Found {scan_result.get('vulnerabilities', 0)} vulnerabilities and {scan_result.get('outdated', 0)} outdated dependencies.",
            severity="info" if scan_result.get('vulnerabilities', 0) == 0 else "warning",
            url=url
        )
        await self.notify(event)

    async def notify_vulnerability(self, repo_full_name: str, vuln_info: dict, url: str | None = None):
        event = NotificationEvent(
            event_type="vulnerability_found",
            repo_full_name=repo_full_name,
            title=f"Vulnerability Found: {vuln_info.get('package_name', 'Unknown')}",
            message=f"A {vuln_info.get('severity', 'high')} severity vulnerability was found in {vuln_info.get('package_name')}.",
            severity="critical",
            url=url
        )
        await self.notify(event)

    async def notify_pr_created(self, repo_full_name: str, pr_info: dict, url: str | None = None):
        event = NotificationEvent(
            event_type="pr_created",
            repo_full_name=repo_full_name,
            title=f"Pull Request Created: {pr_info.get('title', 'Update Dependencies')}",
            message="A new pull request has been automatically created to update dependencies.",
            severity="info",
            url=url
        )
        await self.notify(event)
