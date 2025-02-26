from celery import Celery

from config import RedisConfig


def create_celery_app(name: str, broker: str, backend: str):
    return Celery(
        name,
        broker=broker,
        backend=backend
    )

celery_app = create_celery_app("vegeta", RedisConfig.REDIS_URI, RedisConfig.REDIS_URI)
celery_app.conf.broker_connection_retry_on_startup = True

# 태스크와 인스턴스를 별개의 모듈에서 정의하고, 인스턴스가 정의된 모듈을 celery 명령어의 -A 옵션의 인자로 전달하는 경우
# 태스크를 다음과 같이 직접 찾아준다.

# 1번: autodiscover
# import os
# import sys
# sys.path.insert(0, os.getcwd()) # autodiscover로 가져온 패키지가 루트 경로를 제대로 인식하지 못할 때 직접 설정
# celery_app.autodiscover_tasks(['worker'])

# 2번 conf.import
celery_app.conf.imports = ['worker.tasks']
