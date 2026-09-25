import httpx

from models.notification import JobPayload


class TelegramService:

    def __init__(self, bot_token: str):
        self.bot_token = bot_token

    @staticmethod
    def _build_keyboard(jobs: list[JobPayload]) -> list[list[dict[str, str]]]:
        keyboard: list[list[dict[str, str]]] = []
        for job in jobs:
            link = job.link.strip() if job.link else "#"
            title = (job.title.strip() or "Apply")[:40]
            if not link or link == "#":
                continue
            keyboard.append([{"text": f"Want to apply: {title}", "url": link}])
        return keyboard

    async def send_message(self, chat_id: str, message: str, jobs: list[JobPayload] | None = None) -> bool:

        url = (
            f"https://api.telegram.org/"
            f"bot{self.bot_token}/sendMessage"
        )

        request_body = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        }

        job_buttons = self._build_keyboard(jobs or [])
        if job_buttons:
            request_body["reply_markup"] = {"inline_keyboard": job_buttons}

        try:
            async with httpx.AsyncClient() as client:

                response = await client.post(
                    url,
                    json=request_body,
                    timeout=30.0
                )

                print("Telegram API response:", response.text)

                response.raise_for_status()

                return True

        except Exception as e:

            print("Telegram error:", e)

            return False