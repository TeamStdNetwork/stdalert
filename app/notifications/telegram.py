"""
STD Alert - Telegram Bot Notification Channel

Sends formatted alerts to a Telegram channel/group.
Supports rich formatting with MarkdownV2.
"""

import logging
from datetime import datetime
from typing import Optional

import httpx

from app.notifications.notifier import BaseNotifier, NotificationEvent

logger = logging.getLogger(__name__)

# Telegram Bot API base URL
TELEGRAM_API_BASE = "https://api.telegram.org/bot{token}"


class TelegramNotifier(BaseNotifier):
    """
    Sends notifications to a Telegram channel or group via Bot API.
    
    Setup:
        1. Create a bot via @BotFather on Telegram
        2. Get the bot token
        3. Add the bot to your channel/group as admin
        4. Get the channel/group chat_id
    """

    def __init__(self, bot_token: str, chat_id: str, thread_id: Optional[int] = None):
        """
        Args:
            bot_token: Telegram Bot API token from @BotFather
            chat_id: Channel/group chat ID (e.g., '@your_channel' or '-1001234567890')
            thread_id: Optional topic/thread ID for supergroups with topics enabled
        """
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.thread_id = thread_id
        self.api_base = TELEGRAM_API_BASE.format(token=bot_token)

    async def send(self, event: NotificationEvent) -> bool:
        """Send a formatted notification to Telegram."""
        try:
            message = self._format_message(event)
            return await self._send_message(message)
        except Exception as e:
            logger.error(f"Failed to send Telegram notification: {e}")
            return False

    async def _send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """Send a message via Telegram Bot API."""
        url = f"{self.api_base}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": False,
        }

        if self.thread_id:
            payload["message_thread_id"] = self.thread_id

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload)

            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    logger.info(f"Telegram notification sent to {self.chat_id}")
                    return True
                else:
                    logger.error(f"Telegram API error: {data.get('description')}")
                    return False
            else:
                logger.error(
                    f"Telegram HTTP error: {response.status_code} - {response.text}"
                )
                return False

    def _format_message(self, event: NotificationEvent) -> str:
        """Format notification event into a Telegram-friendly HTML message."""
        severity_emoji = {
            "critical": "🔴",
            "high": "🟠",
            "warning": "🟡",
            "medium": "🟡",
            "info": "🟢",
            "low": "🔵",
        }

        emoji = severity_emoji.get(event.severity, "ℹ️")
        timestamp = event.timestamp.strftime("%Y-%m-%d %H:%M UTC")

        # Build message based on event type
        if event.event_type == "vulnerability_found":
            return self._format_vulnerability(event, emoji, timestamp)
        elif event.event_type == "pr_created":
            return self._format_pr_created(event, emoji, timestamp)
        elif event.event_type == "scan_complete":
            return self._format_scan_complete(event, emoji, timestamp)
        elif event.event_type == "secret_found":
            return self._format_secret_found(event, emoji, timestamp)
        elif event.event_type == "license_issue":
            return self._format_license_issue(event, emoji, timestamp)
        else:
            return self._format_generic(event, emoji, timestamp)

    def _format_vulnerability(
        self, event: NotificationEvent, emoji: str, timestamp: str
    ) -> str:
        return (
            f"🛡️ <b>STD Alert</b>\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"\n"
            f"{emoji} <b>Vulnerability Detected</b>\n"
            f"\n"
            f"📦 <b>Repo:</b> <code>{event.repo_full_name}</code>\n"
            f"⚠️ <b>Severity:</b> {event.severity.upper()}\n"
            f"\n"
            f"📋 <b>Details:</b>\n"
            f"{event.message}\n"
            f"\n"
            f"{f'🔗 <a href=\"{event.url}\">View Details</a>' if event.url else ''}\n"
            f"\n"
            f"🕐 {timestamp}"
        )

    def _format_pr_created(
        self, event: NotificationEvent, emoji: str, timestamp: str
    ) -> str:
        return (
            f"🛡️ <b>STD Alert</b>\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"\n"
            f"✅ <b>Pull Request Created</b>\n"
            f"\n"
            f"📦 <b>Repo:</b> <code>{event.repo_full_name}</code>\n"
            f"📝 <b>Title:</b> {event.title}\n"
            f"\n"
            f"📋 <b>Details:</b>\n"
            f"{event.message}\n"
            f"\n"
            f"{f'🔗 <a href=\"{event.url}\">View PR</a>' if event.url else ''}\n"
            f"\n"
            f"🕐 {timestamp}"
        )

    def _format_scan_complete(
        self, event: NotificationEvent, emoji: str, timestamp: str
    ) -> str:
        return (
            f"🛡️ <b>STD Alert</b>\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"\n"
            f"🔍 <b>Scan Complete</b>\n"
            f"\n"
            f"📦 <b>Repo:</b> <code>{event.repo_full_name}</code>\n"
            f"\n"
            f"📋 <b>Results:</b>\n"
            f"{event.message}\n"
            f"\n"
            f"{f'🔗 <a href=\"{event.url}\">View Dashboard</a>' if event.url else ''}\n"
            f"\n"
            f"🕐 {timestamp}"
        )

    def _format_secret_found(
        self, event: NotificationEvent, emoji: str, timestamp: str
    ) -> str:
        return (
            f"🛡️ <b>STD Alert</b>\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"\n"
            f"🚨 <b>SECRET LEAK DETECTED</b> 🚨\n"
            f"\n"
            f"📦 <b>Repo:</b> <code>{event.repo_full_name}</code>\n"
            f"⚠️ <b>Severity:</b> CRITICAL\n"
            f"\n"
            f"📋 <b>Details:</b>\n"
            f"{event.message}\n"
            f"\n"
            f"⚡ <b>Action Required:</b> Rotate this secret immediately!\n"
            f"\n"
            f"{f'🔗 <a href=\"{event.url}\">View Details</a>' if event.url else ''}\n"
            f"\n"
            f"🕐 {timestamp}"
        )

    def _format_license_issue(
        self, event: NotificationEvent, emoji: str, timestamp: str
    ) -> str:
        return (
            f"🛡️ <b>STD Alert</b>\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"\n"
            f"📜 <b>License Compliance Issue</b>\n"
            f"\n"
            f"📦 <b>Repo:</b> <code>{event.repo_full_name}</code>\n"
            f"\n"
            f"📋 <b>Details:</b>\n"
            f"{event.message}\n"
            f"\n"
            f"🕐 {timestamp}"
        )

    def _format_generic(
        self, event: NotificationEvent, emoji: str, timestamp: str
    ) -> str:
        return (
            f"🛡️ <b>STD Alert</b>\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"\n"
            f"{emoji} <b>{event.title}</b>\n"
            f"\n"
            f"📦 <b>Repo:</b> <code>{event.repo_full_name}</code>\n"
            f"\n"
            f"{event.message}\n"
            f"\n"
            f"{f'🔗 <a href=\"{event.url}\">View</a>' if event.url else ''}\n"
            f"\n"
            f"🕐 {timestamp}"
        )


class TelegramCommandHandler:
    """
    Handle incoming Telegram bot commands for interactive control.
    
    Supported commands:
        /status - Bot status and stats
        /scan <owner/repo> - Trigger manual scan
        /repos - List monitored repositories
        /health <owner/repo> - Get repo health score
        /help - Show available commands
    """

    def __init__(self, bot_token: str):
        self.bot_token = bot_token
        self.api_base = TELEGRAM_API_BASE.format(token=bot_token)

    async def handle_update(self, update: dict) -> None:
        """Process incoming Telegram update."""
        message = update.get("message", {})
        text = message.get("text", "")
        chat_id = message.get("chat", {}).get("id")

        if not text or not chat_id:
            return

        if text.startswith("/"):
            command = text.split()[0].lower().replace("@", " ").split(" ")[0]
            args = text.split()[1:] if len(text.split()) > 1 else []
            await self._handle_command(chat_id, command, args)

    async def _handle_command(
        self, chat_id: int, command: str, args: list[str]
    ) -> None:
        """Route command to appropriate handler."""
        handlers = {
            "/start": self._cmd_start,
            "/help": self._cmd_help,
            "/status": self._cmd_status,
            "/repos": self._cmd_repos,
            "/scan": self._cmd_scan,
            "/health": self._cmd_health,
        }

        handler = handlers.get(command, self._cmd_unknown)
        response = await handler(args)
        await self._reply(chat_id, response)

    async def _reply(self, chat_id: int, text: str) -> None:
        """Send reply message."""
        url = f"{self.api_base}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            await client.post(url, json=payload)

    async def _cmd_start(self, args: list[str]) -> str:
        return (
            "🛡️ <b>Welcome to STD Alert!</b>\n"
            "\n"
            "I monitor your GitHub repositories for:\n"
            "• 📦 Outdated dependencies\n"
            "• 🔐 Security vulnerabilities\n"
            "• 🕵️ Leaked secrets\n"
            "• 📜 License issues\n"
            "\n"
            "Type /help to see available commands."
        )

    async def _cmd_help(self, args: list[str]) -> str:
        return (
            "🛡️ <b>STD Alert Commands</b>\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "\n"
            "/status — Bot status & statistics\n"
            "/repos — List monitored repositories\n"
            "/scan &lt;owner/repo&gt; — Trigger manual scan\n"
            "/health &lt;owner/repo&gt; — Get health score\n"
            "/help — Show this message\n"
        )

    async def _cmd_status(self, args: list[str]) -> str:
        return (
            "🛡️ <b>STD Alert Status</b>\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "\n"
            "✅ Bot is running\n"
            f"🕐 Current time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}\n"
            "\n"
            "📊 Connect the dashboard for detailed stats."
        )

    async def _cmd_repos(self, args: list[str]) -> str:
        return (
            "📦 <b>Monitored Repositories</b>\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "\n"
            "Connect to the dashboard to view all monitored repos.\n"
            "🔗 Visit your dashboard URL /dashboard/"
        )

    async def _cmd_scan(self, args: list[str]) -> str:
        if not args:
            return "⚠️ Usage: /scan &lt;owner/repo&gt;\nExample: /scan facebook/react"
        repo = args[0]
        if "/" not in repo:
            return "⚠️ Invalid format. Use: /scan &lt;owner/repo&gt;"
        return (
            f"🔍 <b>Scan Triggered</b>\n"
            f"\n"
            f"📦 Repo: <code>{repo}</code>\n"
            f"⏳ Scan in progress...\n"
            f"\n"
            f"You'll receive results when the scan completes."
        )

    async def _cmd_health(self, args: list[str]) -> str:
        if not args:
            return "⚠️ Usage: /health &lt;owner/repo&gt;\nExample: /health facebook/react"
        repo = args[0]
        if "/" not in repo:
            return "⚠️ Invalid format. Use: /health &lt;owner/repo&gt;"
        return (
            f"💯 <b>Health Score</b>\n"
            f"\n"
            f"📦 Repo: <code>{repo}</code>\n"
            f"⏳ Calculating...\n"
            f"\n"
            f"Visit the dashboard for detailed health analysis."
        )

    async def _cmd_unknown(self, args: list[str]) -> str:
        return "❓ Unknown command. Type /help to see available commands."
