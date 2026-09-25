import httpx

from models.notification import JobPayload


class WhatsAppService:

    def __init__(
        self,
        access_token: str,
        phone_number_id: str,
        graph_api_version: str
    ):
        self.access_token = access_token
        self.phone_number_id = phone_number_id
        self.graph_api_version = graph_api_version
        print(f"[WhatsApp] initialized with token={self.access_token[:10]}..., phone_number_id={self.phone_number_id}, api_version={self.graph_api_version}")

    @staticmethod
    def _format_message(message: str, jobs: list[JobPayload] | None = None) -> str:
        print(f"[WhatsApp] formatting message with {len(jobs) if jobs else 0} jobs")
        return message

    async def send_message(
        self,
        phone_number: str,
        message: str,
        jobs: list[JobPayload] | None = None,
    ) -> bool:
        print(f"[WhatsApp] start send_message to={phone_number}")
        print(f"[WhatsApp] raw message length={len(message)}")
        print(f"[WhatsApp] job count={len(jobs) if jobs else 0}")

        url = (
            f"https://graph.facebook.com/"
            f"{self.graph_api_version}/"
            f"{self.phone_number_id}/messages"
        )

        formatted_message = self._format_message(message, jobs)
        request_body = {
            "messaging_product": "whatsapp",
            "to": phone_number,
            "type": "text",
            "text": {
                "body": formatted_message
            }
        }

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

        print(f"[WhatsApp] target URL={url}")
        print(f"[WhatsApp] message preview={formatted_message[:200]}")
        print(f"[WhatsApp] auth header present={bool(self.access_token)}")

        try:
            async with httpx.AsyncClient() as client:
                print("[WhatsApp] making HTTP POST request...")
                response = await client.post(
                    url,
                    headers=headers,
                    json=request_body,
                    timeout=30.0
                )

                print(f"[WhatsApp] response status={response.status_code}")
                print(f"[WhatsApp] response body={response.text}")

                try:
                    response.raise_for_status()
                except Exception as exc:
                    print(f"[WhatsApp] raise_for_status failed: {exc}")
                    return False

                print("[WhatsApp] message sent successfully")
                return True

        except Exception as e:
            print(f"[WhatsApp] exception in send_message: {repr(e)}")
            return False