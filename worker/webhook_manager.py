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
        self.endpoint = WebhookConfig.WEBHOOK_CALLBACK_BASE_ENDPOINT
        self.path_mapping = {
            TestCaseResult: "/test-case-result",
            PassedJudgment: "/judgment-passed",
            UnpassedJudgment: "/judgment-unpassed",
            Error: "/error"
        }
        self.default_path = self.path_mapping[Error]

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

    async def dispatch_webhook_callback(self, event):
        """
        웹훅 요청(HTTP 비동기 요청)에 대한 콜백(웹훅 요청에 대해, 웹훅 수신자가 응답을 비동기적 HTTP 요청으로 처리하는 것)을 전달하는 메서드.
        발생한 이벤트 종류에 따라 웹훅 클라이언트 서버(HTTP 비동기 요청을 주문한 서버)의 엔드포인트로 웹훅 콜백을 전달.

        웹훅 호출에 대한 결과를 비동기 HTTP 요청(콜백)으로 웹훅 호출자에게 전달합니다.
        주어진 이벤트 타입에 따라 적절한 엔드포인트로 POST 요청을 보내고,
        성공 시 HTTP 상태 코드(200~299), 실패 시 에러 코드를 반환합니다.
        """
        url = self.endpoint + self.path_mapping.get(type(event), self.default_path)

        try:
            # aiohttp로 비동기 POST 요청
            # async with 구문은 요청이 끝나면 자동으로 리소스를 정리
            async with self.session.post(
                url,
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
