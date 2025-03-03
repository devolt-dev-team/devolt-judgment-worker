import asyncio # 비동기 작업을 처리하기 위한 파이썬 기본 라이브러리입니다. async와 await를 키워드를 통한 코루틴 작업을 통해 여러 작업을 동시에 실행할 수 있게 해줍니다.
import base64
import os
import random
import string
import json
import tempfile
import logging

from common import *
from config import DockerConfig
from schema import Verdict
from schema.webhook_event import TestCaseResult, Error, SubmissionResult
from schema.job import CodeChallengeJudgmentJob as Job
from redisutil.repository import job_repository
from worker.webhook_manager import AsyncWebhookManager


def _create_random_string(length: int = 8) -> str:
    """랜덤 문자열 생성 (소문자 + 숫자 조합)

    Args:
        length (int): 생성할 문자열 길이 (기본값 8)

    Returns:
        str: 생성된 랜덤 문자열

    Notes:


    Example:
        >>> _create_random_string(6)
        'a3b8f2'
    """
    chars = string.ascii_lowercase + string.digits
    return ''.join(random.choice(chars) for _ in range(length))


def _build_docker_run_cmd(
    tmp_code_path: str,
    docker_image_name: str,
    test_cases: tuple[tuple[list, str]],
    test_case_memory_limit_mb: int,
    test_case_time_limit_sec: float,
    cpu_core_limit: float = 0.5
) -> list[str]:
    """도커 실행 명령어 생성 함수

    코드 채점을 위한 도커 컨테이너 실행 명령어를 생성합니다. 보안 및 리소스 제한 설정을 포함합니다.

    Args:
        tmp_code_path (str): temp 코드 파일 경로
        docker_image_name (str): 사용할 도커 이미지 이름
        test_cases (tuple): 테스트 케이스 튜플 (입력값, 기대출력) 리스트
        test_case_memory_limit_mb (int): 테스트케이스 메모리 제한(MB)
        test_case_time_limit_sec (float): 테스트케이스 실행 시간 제한(초)
        cpu_core_limit (float): 실행 환경 할당 CPU 코어 수

    Notes:
        cpu_core_limit의 경우 사양에 따라 min 값을 1정도로 기본 값을 할당 해도 괜찮음
        또는 외부에서 테스트 케이스 별로 설정하는 방식으로 사용 가능

    Returns:
        list[str]: 도커 실행 명령어 리스트
    """
    # 코드 임시 파일에서 경로 제거, 파일 이름만 추출
    code_filename = os.path.basename(tmp_code_path)

    # tmpfs 경로 설정
    tmpfs_path = f"/tmp/{_create_random_string()}"

    # 문제에 따라 조정이 필요한 경우 다른 상수 값 처럼 문제 별로 설정한 값을 할당할 것
    pids_limit = 300

    return [
        "docker", "run", "--rm", "-t",                                                          # --rm: 컨테이너가 종료될 때 컨테이너와 관련된 리소스(파일 시스템, 볼륨) 제거, -t: 컨테이너 출력을 즉시 read하기 위해 컨테이너에 가상 TTY 할당하고 subprocess의 I/O 스트림과 직접 연결
        "--network", "none",                                                                    # 네트워크 차단
        "--mount", f"type=bind,source={tmp_code_path},target=/tmp/{code_filename},readonly",    # 코드는 파일로 전달, /tmp는 Linux 표준 임시 디렉토리
        "--mount", f"type=tmpfs,destination={tmpfs_path}",                                      # 컨테이너 내부에서 쓰기 가능한 tmpfs 마운트 경로 설정, 메모리 기반 파일 시스템
        "--read-only",                                                                          # 파일 시스템은 기본적으로 읽기 전용 설정
        "--memory", f"{test_case_memory_limit_mb + 64}m",                                       # 컨테이너 메모리 제한 (컨테이너 유지 비용, time 실행 비용, tmpfs 유지 비용을 고려, 여유분 64mb 추가 할당), 내부 하위 프로세스는 메모리 사용 초과 시 SIGKILL 처리 되어 -9 반환하고 종료됨
        "--cpus", f"{cpu_core_limit}",                                                          # CPU 코어 수 제한 (서버 사양에 따라 여유가 있다면 1로 설정해도 괜찮음)
        "--pids-limit", f"{pids_limit}",                                                        # 프로세스 수 제한
        "--cap-drop", "ALL",                                                                    # 기본적으로 부여되는 모든 권한을 제거하고, 최소한의 권한만 사용하도록 설정
        docker_image_name,                                                                      # 도커 이미지 설정

        # Dockerfile에 설정된 ENTRYPOINT과 함께 전달할 argument 목록
        code_filename,                                                                          # 코드 임시 파일 경로
        tmpfs_path,                                                                             # tmpfs 마운트 경로
        json.dumps(test_cases),                                                                 # 테스트 케이스 입력 및 정답 튜플 (JSON 직렬화)
        str(test_case_memory_limit_mb),                                                         # 테스트 케이스 메모리 제한
        str(test_case_time_limit_sec)                                                           # 테스트 케이스 실행 시간 제한
    ]


async def handle_webhook_response(
    future: asyncio.Future,
    proc: asyncio.subprocess.Process,
    cleanup_job_and_return_event: asyncio.Event,
    job_id: str
) -> None:
    """웹훅 응답 처리 코루틴

    웹훅 전송 결과를 처리하고 실패 시 리소스 정리 작업을 수행합니다.

    Args:
        future (Future): 웹훅 전송 Future 객체
        proc (Process): 실행 중인 도커 프로세스
        cleanup_job_and_return_event (Event): 채점 실패/불가한 경우, 리소스 정리 및 메인 프로세스 종료를 예약하기 위한 이벤트
        job_id (str): 작업 ID

    Returns:
        None
    """
    response_code = await future
    if response_code != 200:
        logging.error(f"Webhook failed with code {response_code} for job {job_id}")
        if proc.returncode is None:  # 프로세스가 아직 살아있을 때만 kill
            proc.kill()
        cleanup_job_and_return_event.set()


async def async_handle_output(
    stream: asyncio.StreamReader,
    proc: asyncio.subprocess.Process,
    cleanup_job_and_return_event,
    job_id: str,
    verdicts: list[Verdict],
    webhook_manager: AsyncWebhookManager,
    tasks: list[asyncio.Task]
) -> None:
    try:
        while True:
            line = await stream.readline()
            if not line:
                break

            line = line.decode('utf-8').strip()
            logging.info(f"[DEBUG]Output from sandbox process:{line}")

            if line.startswith("VERDICT:"):
                verdict = Verdict.create_from_dict(json.loads(line[len("VERDICT:"):]))
                verdicts.append(verdict)

                webhook_event = TestCaseResult(job_id, verdict)
                future = asyncio.ensure_future(webhook_manager.send_webhook(webhook_event))
                tasks.append(asyncio.create_task(handle_webhook_response(future, proc, cleanup_job_and_return_event, job_id)))

            elif line.startswith("SYSTEM_ERROR:"):
                error_dict = json.loads(line[len("SYSTEM_ERROR:"):])
                logging.error(f"[Unexpected error in sandbox for job {job_id}. Error: {error_dict['error']}]")

                # proc.kill()은 생략해도 ok (proc은 SYSTEM_ERROR 출력 후 자동으로 종료됨)
                cleanup_job_and_return_event.set()
                await webhook_manager.send_webhook(Error(job_id))
                break

            else:
                raise Exception(f"Unexpected output: {line}")

    except Exception as ex:
        logging.error(f"[{job_id} Output handling error]", exc_info=True)

        proc.kill()
        cleanup_job_and_return_event.set()
        await webhook_manager.send_webhook(Error(job_id))


async def async_execute_code(user_id: int, job: Job, webhook_manager: AsyncWebhookManager):
    try:
        # 코드 디코딩 및 준비
        code_decoded = base64.b64decode(job.code).decode("utf-8")
        test_cases = TEST_CASES[job.challenge_id]

        # 소스 코드 파일 생성
        file_extension = {
            'java17': '.java',
            'nodejs20': '.js',  # CommonJS
            'nodejs20esm': '.mjs',  # ESM
            'python3': '.py',
        }.get(job.code_language)

        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', delete=False, suffix=file_extension) as tmp:
            tmp.write(code_decoded)
            tmp_code_path = tmp.name

        test_case_memory_limit = TEST_CASE_EXEC_MEM_LIMIT[job.challenge_id] + get_memory_bonus_by_language(job.code_language, job.challenge_id)
        test_case_time_limit = TEST_CASE_EXEC_TIME_LIMIT[job.challenge_id] + get_time_bonus_by_language(job.code_language)

        # Docker 명령어 생성
        docker_cmd = _build_docker_run_cmd(
            tmp_code_path,
            DockerConfig.DOCKER_IMAGE[job.code_language],
            random.sample(test_cases, len(test_cases)),
            test_case_memory_limit,
            test_case_time_limit
        )

        # 비동기 서브프로세스 실행
        sandbox_proc = await asyncio.create_subprocess_exec(
            *docker_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        tasks = []
        verdicts = []
        cleanup_job_and_return_event = asyncio.Event()

        # 출력 처리 백그라운드 작업 실행
        # asyncio에 의해 자동으로 스케줄링
        stdout_task = asyncio.create_task(
            async_handle_output(sandbox_proc.stdout, sandbox_proc, cleanup_job_and_return_event, job.job_id, verdicts, webhook_manager, tasks)
        )
        stderr_task = asyncio.create_task(
            async_handle_output(sandbox_proc.stderr, sandbox_proc, cleanup_job_and_return_event, job.job_id, verdicts, webhook_manager, tasks)
        )

        tasks.append(stdout_task)
        tasks.append(stderr_task)

        # 샌드박스 타임아웃 설정
        max_compile_time_limit = 5.0
        total_timeout = len(test_cases) * test_case_time_limit + max_compile_time_limit + 10.0 # 오버 헤드 감안 10.0초 추가 할당
        try:
            await asyncio.wait_for(sandbox_proc.wait(), timeout=total_timeout)
        except asyncio.TimeoutError:
            # sandbox_proc에 SIGKILL 전달
            # 프로세스가 종료, 도커 관련 리소스는 Docker 데몬이 백그라운드에서 처리
            sandbox_proc.kill()
            cleanup_job_and_return_event.set()
            await webhook_manager.send_webhook(Error(job.job_id, "채점 실행 시간 최대 허용 한도 초과"))

        # Thread.join()과 유사하게, 백그라운드 작업(모든 테스트 케이스에 대한 verdict 전달) 완료 시점까지 대기
        await asyncio.gather(*tasks)

        # 하위 task의 채점 실패/불가 이벤트 확인
        if cleanup_job_and_return_event.is_set():
            job_repository.delete(job.job_id, user_id)
            return

        overall_pass = True
        max_memory_used_mb = -1.0
        max_elapsed_time_sec = -1.0
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
            max_memory_used_mb = max(max_memory_used_mb, d.get('memoryUsedMb'))
            max_elapsed_time_sec = max(max_elapsed_time_sec, d.get('elapsedTimeSec'))

        # 최종 채점 결과 전송
        result = SubmissionResult(
            user_id=user_id,
            job_id=job.job_id,
            challenge_id=job.challenge_id,
            code_language=job.code_language,
            code=job.code,
            code_byte_size=len(job.code),
            overall_pass=overall_pass,
            max_memory_used_mb=max_memory_used_mb,
            max_elapsed_time_sec=max_elapsed_time_sec,
            compile_error=compile_error,
            runtime_error=runtime_error,
            submitted_at=job.submitted_at
        )

        await webhook_manager.send_webhook(result)
        job_repository.delete(job.job_id, user_id)

    # finally는 os._exit(code)를 호출하는 경우(os.exit(code)와 다름)를 제외하고
    # 항상 실행 됨
    finally:
        await webhook_manager.shutdown()
        if tmp_code_path and os.path.exists(tmp_code_path):
            os.remove(tmp_code_path)
        # asyncio의 이벤트 루프가 프로세스 종료 시(sandbox_proc.returncode가 설정된 후),
        # 내부적으로 파이프(sandbox_proc.stdout, sandbox_proc.stderr)는 자동으로 close
        # subprocess.Popen를 직접 사용하는 경우, pipe 수명 관리를 직접 해야함
