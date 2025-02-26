import json
from typing import Optional, Union
import logging
import time

from redisutil import RedisConnection, RedisConnectionError
from schema import Verdict
from schema.job import CodeChallengeJudgmentJob as Job


class CodeChallengeJudgmentJobRepository:
    """
    코딩 테스트 작업(Job) 정보를 Redis에 CRUD하는 메서드를 제공하는 클래스.
    """

    def __init__(self, redis_conn: RedisConnection):
        self._redis_client = redis_conn.client


    def find_by_user_id(self, user_id: int) -> list[Job]:
        key_pattern = f"{user_id}:*"
        # Redis 조회는 기본적으로 str 반환, Redis encode/decode 관련 설정에 따라 bytes 타입이 반환될 수 있음
        keys: list[Union[str, bytes]] = list(self._with_retry(
            self._redis_client.scan_iter, key_pattern
        ))

        jobs: list[Job] = []
        for key in keys:
            job_data: Union[str, bytes, None] = self._with_retry(
                self._redis_client.get, key
            )
            if job_data:
                if isinstance(job_data, bytes):
                    job_data = job_data.decode("utf-8") # bytes 타입인 경우 디코딩하여 str 타입으로 변환
                jobs.append(Job.create_from_dict(json.loads(job_data)))
        return jobs


    def find_user_id_by_job_id(self, job_id: str) -> int:
        key_pattern = f"*:{job_id}"

        key: Union[str, bytes, None] = self._with_retry(
            # next(iterator, default_value)를 사용하여 첫 번째 값만 가져오고 반복 중단
            lambda _key_pattern: next(self._redis_client.scan_iter(_key_pattern), None), key_pattern
        )

        if not key:
            return -1

        if isinstance(key, bytes):
            key = key.decode("utf-8")

        user_id_str = key.split(":", 1)[0] # 1회만 분할하여 리스트로 구분 후 0번 요소 추출
        return int(user_id_str)


    def find_by_job_id(self, job_id: str) -> Optional[Job]:
        user_id: int = self.find_user_id_by_job_id(job_id)
        if user_id == -1:
            return None

        return self.find_by_user_id_and_job_id(user_id, job_id)


    def find_by_user_id_and_job_id(self, user_id: int, job_id: str) -> Optional[Job]:
        key = f"{user_id}:{job_id}"

        job = None
        # get 반환 값 -> value 존재: str/bytes, value 존재 X: None
        job_data: [str, bytes, None] = self._with_retry(
            self._redis_client.get, key
        )
        if job_data:
            if isinstance(job_data, bytes):
                job_data = job_data.decode("utf-8") # bytes 타입인 경우 디코딩하여 str 타입으로 변환
            job = Job.create_from_dict(json.loads(job_data))
        return job


    def save(self,
        user_id: int,
        job: Job,
        ttl: int
    ) -> int:
        key = f"{user_id}:{job.job_id}"

        return 1 if self._with_retry(
            self._redis_client.setex, key, ttl, json.dumps(job.as_dict())
        ) else 0


    def delete(self,
        job_id: str,
        user_id: int = None
    ) -> int:
        if user_id is None:
            user_id = self.find_user_id_by_job_id(job_id)
            if user_id == -1:
                return -1

        key = f"{user_id}:{job_id}"

        # 삭제된 데이터 수 반환
        return self._with_retry(
            self._redis_client.delete, key
        )


    def update(self,
        job_id: str,
        user_id: int = None,
        stop_flag: bool = None,
        last_test_case_index: int = None,
        verdicts: list[Verdict] = None
    ) -> int:
        if user_id is None:
            user_id: int = self.find_user_id_by_job_id(job_id)
            if user_id == -1:
                return -1

        job = self.find_by_user_id_and_job_id(user_id, job_id)

        key = f"{user_id}:{job_id}"
        if not job:
            return -1

        # 기존 키의 TTL 조회
        ttl_value = self._with_retry(
            self._redis_client.ttl, key
        )

        if ttl_value < 0:
            # -1 => ttl 설정되지 않은 상태 (로직 상 존재 불가능)
            # -2 => key가 존재하지 않음
            if ttl_value == -1:
                self.delete(job_id, user_id)
            return -1

        if stop_flag is not None:
            job.stop_flag = stop_flag

        if last_test_case_index is not None:
            job.last_test_case_index = last_test_case_index

        if verdicts is not None:
            job.verdicts = verdicts

        return self.save(user_id, job, ttl_value)


    # 필드에 의존하지 않는 메서드 이므로 static으로 처리
    # kwargs는 args와 같이 쓸 경우, args 뒤에 와야함
    # args는 연속된 변수를 tuple에 순서대로 담고
    # kwargs는 keyword=value와 같이 주어진 값을 하나의 dict로 변환 묶어 다루도록 해줌
    @staticmethod
    def _with_retry(func: callable, *args, **kwargs) -> any:
        """
        전달된 Redis 관련 CRUD 작업 실패 시 재시도를 수행하는 메서드
        - func: 실행할 함수 (예: self.client.get, self.client.setex 등)
        - args, kwargs: 함수에 전달될 인자
        """

        max_retries = 3 # 최대 재시도 횟수
        retry_interval = 0.5 # 재시도 간격 (단위: 초)
        for attempt in range(1, max_retries + 1):
            try:
                return func(*args, **kwargs)
            except Exception as ex:
                func_name = getattr(func, '__name__', repr(func))
                logging.error(
                    f"[(Attempt: ({attempt}/{max_retries}) JobRepository >> {func_name} throw unexpected exception: {ex}]")
                if attempt < max_retries:
                    time.sleep(retry_interval)
                    retry_interval *= 2
                else:
                    raise  # 최종 실패 시 func에서 발생한 예외를 그대로 throw -> 상위에서 처리


from config import RedisConfig
try:
    job_repository = CodeChallengeJudgmentJobRepository(
        RedisConnection(
            host=RedisConfig.HOST,
            port=RedisConfig.PORT,
            password=RedisConfig.PASSWORD,
            db=RedisConfig.DB
        )
    )
except RedisConnectionError as ex:
    logging.error(ex)
    exit(1)