import base64
import random
import tempfile
import subprocess
import os

from config import DockerConfig
from redisutil.repository import job_repository
from worker import celery_app as app
from worker.helpers import *
from schema.job import CodeChallengeJudgmentJob as Job
from common import TEST_CASES, TEST_CASE_EXECUTION_MEMORY_LIMIT, TEST_CASE_EXECUTION_TIME_LIMIT


# task에 매개변수를 전달하는 경우, 콜백 함수는 self를 인자로 받아야 한다.
@app.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={'max_retries': 3})
def execute_code(self, user_id: int, job_dict: dict):
    """
    Celery 작업: 코드를 채점하고 Webhook 엔드포인트로 실행 결과를 실시간으로 전달합니다.

    Args:
        job_dict (dict): 실행 할 작업 정보
    """
    # 샌드박스 실행 프로세스를 유지하는 변수
    docker_sandbox_proc = None
    job = Job.create_from_dict(job_dict)

    # try-finally 구문:
    # 예외가 발생한 위치에서 즉시 실행이 중단되고 finally 실행 후 상위로 예외 전파
    try:
        code_decoded_bytes = base64.b64decode(job.code)
        code_byte_size = len(code_decoded_bytes)
        code_decoded = code_decoded_bytes.decode("utf-8")

        test_cases = TEST_CASES[job.challenge_id]
        test_case_memory_limit_mb: int = TEST_CASE_EXECUTION_MEMORY_LIMIT[job.challenge_id]
        test_case_time_limit_sec: float = TEST_CASE_EXECUTION_TIME_LIMIT[job.challenge_id]

        if job.code_language == 'java':
            test_case_memory_limit_mb *= 2
            test_case_time_limit_sec *= 2
        elif job.code_language in ['python', 'nodejs']:
            test_case_memory_limit_mb *= 2
            test_case_time_limit_sec *= 3

        # 채점 결과 저장
        verdicts: list[Verdict] = []

        # 코드를 저장하는 임시 파일 생성
        # delete=False를 주어 컨테이너 내부 마운트 이전에 삭제되지 않도록 처리
        with tempfile.NamedTemporaryFile(mode='w', encoding="utf-8", delete=False) as tmp:
            tmp.write(code_decoded)
            tmp_code_path = tmp.name

        docker_run_cmd = build_docker_run_cmd(
            tmp_code_path,
            DockerConfig.DOCKER_IMAGE[job.code_language],
            random.sample(test_cases, len(test_cases)), # 테스트 케이스 실행 순서 무작위로 설정
            test_case_memory_limit_mb,
            test_case_time_limit_sec
        )

        # Docker 컨테이너 실행 (실시간 스트리밍을 위해 bufsize=1, text=True 설정)
        # bufsize=1을 설정하여 Python이 해당 출력을 읽어올 때 라인 단위로 처리하도록 설정
        # subprocess.run은 Popen을 더 간편하게 사용하기 위한 새로운 함수이며, 동기적으로 동작
        # Popen은 비동기 동작
        docker_sandbox_proc = subprocess.Popen(
            docker_run_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True, bufsize=1
        )

        # 스레드간 컨텍스트를 공유하기 위한 Event 객체
        cleanup_job_event = threading.Event()

        # stdout과 stderr를 읽는 스레드 생성
        stdout_reader_thread = threading.Thread(target=handle_output, args=(
            docker_sandbox_proc.stdout,
            "stdout",
            docker_sandbox_proc,
            cleanup_job_event,
            user_id,
            job.job_id,
            verdicts,
        ))
        stderr_reader_thread = threading.Thread(target=handle_output, args=(
            docker_sandbox_proc.stderr,
            "stderr",
            docker_sandbox_proc,
            cleanup_job_event,
            user_id,
            job.job_id,
            verdicts,
        ))

        stdout_reader_thread.start()
        stderr_reader_thread.start()

        # Docker run 프로세스 종료까지 대기
        # 전체 타임아웃 계산: 각 테스트 케이스 실행 시간 + 5초(컴파일 시간) + 5초(기타 오버헤드)
        total_timeout = len(test_cases) * test_case_time_limit_sec + 10.0
        try:
            docker_sandbox_proc.wait(timeout=total_timeout)
        except subprocess.TimeoutExpired:
            # kill() 메서드 호출하여 해당 프로세스에 SIGKILL을 전달
            # subprocess로 생성한 프로세스가 정리되고,
            # 이와 별개로 백그라운드에서 Docker 데몬에 의해 자동으로 도커 컨테이너 관련 리소스가 정리 작업이 수행됨
            docker_sandbox_proc.kill()

        # 자식 스레드가 종료될 때까지 호출한(메인) 스레드를 블로킹
        # 자식 스레드에서 작업이 완료되기 전에 메인 프로세스가 진행되지 않도록 보장
        stdout_reader_thread.join()
        stderr_reader_thread.join()

        if cleanup_job_event.is_set():
            job_repository.delete(job.job_id, user_id)

    except Exception as ex:
        logging.error(f"[{job.job_id} 작업 실행 중 처리되지 않은 예외가 발생했습니다]", exc_info=True)
        job_repository.delete(job.job_id, user_id)

        send_webhook(Error(job.job_id))
        return # finally 작업 실행은 보장됨

    finally:
        # 컨테이너 실행 후 임시 파일 삭제
        if os.path.exists(tmp_code_path):
            os.remove(tmp_code_path)

        # pipe 리소스 할당 해제
        if docker_sandbox_proc and docker_sandbox_proc.stdout and not docker_sandbox_proc.stdout.closed:
            docker_sandbox_proc.stdout.close()
        if docker_sandbox_proc and docker_sandbox_proc.stderr and not docker_sandbox_proc.stderr.closed:
            docker_sandbox_proc.stderr.close()

    overall_pass = True
    max_memory_used_mb = 0
    max_elapsed_time_sec = 0
    compile_error = None
    runtime_error = None

    for verdict in verdicts:
        if verdict.compile_error or verdict.runtime_error or not verdict.passed:
            overall_pass = False
            max_memory_used_mb = None
            max_elapsed_time_sec = None
            compile_error = verdict.compile_error
            runtime_error = verdict.runtime_error
            break

        d = verdict.as_dict()
        max_memory_used_mb = max(max_memory_used_mb, d.get('memoryUsedMb', 0))
        max_elapsed_time_sec = max(max_elapsed_time_sec, d.get('elapsedTimeSec', 0))

    result = SubmissionResult(
        user_id,
        job.job_id,
        job.challenge_id,

        job.code_language,
        job.code,
        code_byte_size,

        overall_pass,
        max_memory_used_mb,
        max_elapsed_time_sec,

        compile_error,
        runtime_error,

        job.submitted_at
    )

    if send_webhook(result) == 200:
        job_repository.delete(job.job_id, user_id)
    else:
        logging.error(f"[채점 완료 결과를 수신하지 못하여 Redis에 job {job.job_id} 데이터를 유지합니다]")

    logging.info(f"[Job {job.job_id} complete successfully...]")
