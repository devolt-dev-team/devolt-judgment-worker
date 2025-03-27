from worker import celery_app as app
from worker.helpers import *
from schema.job import CodeChallengeJudgmentJob as Job

@app.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={'max_retries': 3})
def execute_code(self, user_id: int, job_dict: dict):
    job = None
    loop = None
    webhook_manager = None

    try:
        job = Job.create_from_dict(job_dict)
        loop = asyncio.new_event_loop()
        webhook_manager = AsyncWebhookManager()

        # AsyncWebhookManager 초기화
        loop.run_until_complete(webhook_manager.initialize())
        loop.run_until_complete(async_execute_code(user_id, job, webhook_manager))
    except Exception as e:
        if not job or not loop or not webhook_manager: raise
        logging.error(f"작업 실행 중 처리되지 않은 예외 발생\n작업 정보: {job_dict}", exc_info=True)
        job_repository.delete(job.job_id, user_id)
        loop.run_until_complete(webhook_manager.dispatch_webhook_callback(Error(job.job_id)))
    finally:
        if loop and webhook_manager:
            loop.run_until_complete(webhook_manager.shutdown())
        if loop:
            loop.close()
