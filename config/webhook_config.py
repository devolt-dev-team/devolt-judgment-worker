from common import get_env_var


class WebhookConfig:
    """
    Description:
        WebHook 설정 정보를 관리하는 클래스.
    """
    WEBHOOK_NOTIFY_VERDICT_ENDPOINT = get_env_var("WEBHOOK_NOTIFY_VERDICT_ENDPOINT")
    WEBHOOK_NOTIFY_SUBMISSION_RESULT_ENDPOINT = get_env_var("WEBHOOK_NOTIFY_SUBMISSION_RESULT_ENDPOINT")
    WEBHOOK_NOTIFY_ERROR_ENDPOINT = get_env_var("WEBHOOK_NOTIFY_ERROR_ENDPOINT")
