from models.notification import JobPayload, NotificationRequest
from services.telegram_service import TelegramService
from services.whatsapp_service import WhatsAppService


class NotificationService:

    def __init__(
        self,
        telegram_service: TelegramService,
        whatsapp_service: WhatsAppService
    ):
        self.telegram_service = telegram_service
        self.whatsapp_service = whatsapp_service

    @staticmethod
    def _format_jobs_message(jobs: list[JobPayload]) -> str:
        if not jobs:
            return "No jobs to share."

        sections: list[str] = [
            "🚀 New job opportunities for you",
            "",
        ]

        for index, job in enumerate(jobs, start=1):
            title = job.title.strip() or "Untitled role"
            company = job.company.strip() or "Unknown company"
            location = job.location.strip() or "Remote / India"
            source = job.source.strip() or "Source"
            credibility = job.credibility_score if job.credibility_score is not None else "N/A"
            scraped_at = job.scraped_at or "N/A"
            button_link = job.link.strip() if job.link else "#"

            sections.append(f"{index}. {title}")
            sections.append(f"   🏢 {company}")
            sections.append(f"   📍 {location}")
            sections.append(f"   🔤 {source}")
            sections.append(f"   ⭐ Credibility: {credibility}")
            sections.append(f"   🕒 Scraped: {scraped_at}")
            if button_link and button_link != "#":
                sections.append(f"   🔗 Apply: {button_link}")
            sections.append("")

        footer = "✅ Tap the Apply link to open the listing."
        return "\n".join(sections + [footer])

    async def send(
        self,
        request: NotificationRequest
    ) -> bool:

        channel = request.channel.strip().lower()
        message = request.message
        print(f"[NotificationService] channel={channel}, recipient={request.recipient}, jobs={len(request.jobs) if request.jobs else 0}")

        if request.jobs:
            message = self._format_jobs_message(request.jobs)
            print(f"[NotificationService] formatted message length={len(message)}")

        if not message:
            print("[NotificationService] no message to send; aborting")
            return False

        if channel == "telegram":
            print("[NotificationService] delegating to Telegram service")
            return await self.telegram_service.send_message(
                request.recipient,
                message,
                request.jobs,
            )

        elif channel == "whatsapp":
            print("[NotificationService] delegating to WhatsApp service")
            return await self.whatsapp_service.send_message(
                request.recipient,
                message,
                request.jobs,
            )

        print(f"[NotificationService] unsupported channel: {channel}")
        return False