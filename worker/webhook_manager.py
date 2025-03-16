import aiohttp  # 비동기 HTTP 요청을 보내기 위한 라이브러리입니다. requests 대신 사용되며, 네트워크 요청을 기다리지 않고 다른 작업을 처리할 수 있습니다.
import logging

from config import WebhookConfig
from schema.webhook_event import *


class AsyncWebhookManager:
    """
    웹훅(서버가 다른 서버로 이벤트를 알리는 요청)을 비동기적으로 처리하는 클래스.
    """

    def __init__(self):
        """
        HTTP 요청 시 세션을 재사용하기 위해 세션 객체를 속성으로 유지.
        """
        self.session = None

    async def initialize(self):
        """
        클래스 초기화 메서드. 비동기 HTTP 요청을 처리하기 위한 aiohttp 세션을 초기화.
        """
        self.session = aiohttp.ClientSession()

    async def shutdown(self):
        """
        클래스를 안전하게 종료하기 위해 세션을 정리.
        """
        # 리소스 누수를 방지하기 위해 세션이 열려 있다면 닫기
        if self.session:
            await self.session.close()

    async def send_webhook(self, event):
        """
        웹훅을 보내는 메서드. 주어진 이벤트에 따라 적절한 엔드포인트로 HTTP POST 요청.
        """
        endpoint_mapping = {
            TestCaseResult: WebhookConfig.WEBHOOK_NOTIFY_VERDICT_ENDPOINT,
            PassedJudgment: WebhookConfig.WEBHOOK_NOTIFY_SUBMISSION_RESULT_ENDPOINT,
            UnpassedJudgment: WebhookConfig.WEBHOOK_NOTIFY_SUBMISSION_RESULT_ENDPOINT,
            Error: WebhookConfig.WEBHOOK_NOTIFY_ERROR_ENDPOINT
        }
        endpoint = endpoint_mapping.get(type(event), WebhookConfig.WEBHOOK_NOTIFY_ERROR_ENDPOINT)

        try:
            # aiohttp로 비동기 POST 요청
            # async with 구문은 요청이 끝나면 자동으로 리소스를 정리
            async with self.session.post(
                endpoint,
                json=event.as_dict(),
                headers={'Content-Type': 'application/json'},
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                # 응답이 성공(200~299)인지 확인. 실패하면 예외 발생
                response.raise_for_status()
                return response.status
        except aiohttp.ClientResponseError as e:
            logging.error(f"Webhook error: {str(e)}")
            return e.status
        except Exception as e:
            logging.error(f"Webhook error: {str(e)}")
            return 500
