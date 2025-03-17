import asyncio # 비동기 작업을 처리하기 위한 파이썬 기본 라이브러리입니다. async와 await를 키워드를 통한 코루틴 작업을 통해 여러 작업을 동시에 실행할 수 있게 해줍니다.
import base64
import random
import tempfile
import logging

from common import *
from config import DockerConfig
from schema import Verdict
from schema.webhook_event import *
from schema.job import CodeChallengeJudgmentJob as Job
from redisutil.repository import job_repository
from worker.webhook_manager import AsyncWebhookManager


def _build_docker_run_cmd(
    tmp_code_path: str,
    code_language: str,
    test_cases: tuple[tuple[list, str]],
    test_case_memory_limit_mb: int,
    test_case_time_limit_sec: float,
    cpu_core_limit: float = 0.5
) -> list[str]:
    """도커 실행 명령어 생성 함수

    코드 채점을 위한 도커 컨테이너 실행 명령어를 생성합니다. 보안 및 리소스 제한 설정을 포함합니다.

    Args:
        tmp_code_path (str): temp 디렉토리에 생성된 코드 파일 경로
        code_language (str): 프로그래밍 언어
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

    # tmp_code_path에서 디렉터리 정보, 파일 이름 분리
    tmp_directory_path, code_file_name = os.path.split(tmp_code_path)

    # seccomp 보안 프로필 경로 로드
    seccomp_profile_path = DockerConfig.SECCOMP_PROFILE_PATH

    # 샌드박스 이미지 및 스크립트 경로 로드
    sandbox_image = DockerConfig.SANDBOX_IMAGE_NAME[code_language]
    sandbox_script_path = DockerConfig.SANDBOX_SCRIPT_PATH[code_language]

    # 내부 프로세스 수 상한
    pids_limit = 50

    return [
        "docker", "run", "--rm", "-t",                                                                  # --rm: 컨테이너가 종료될 때 컨테이너와 관련된 리소스(파일 시스템, 볼륨) 제거, -t: 컨테이너 출력을 즉시 read하기 위해 컨테이너에 가상 TTY 할당하고 subprocess의 I/O 스트림과 직접 연결

        "--mount", f"type=bind,source={tmp_directory_path},target=/tmp",                                # 컨테이너 내부에서 쓰기 가능한 파일 시스템 마운트
        "--mount", f"type=bind,source={tmp_code_path},target=/tmp/{code_file_name},readonly",    # 소스코드 마운트
        "--mount", f"type=bind,source={sandbox_script_path},target=/tmp/run.sh,readonly",               # 채점 스크립트 마운트
        "--read-only",                                                                                  # 파일 시스템은 기본적으로 읽기 전용 설정

        "--ulimit", "nofile=32:32",                                                                     # 열 수 있는 파일 수 제한
        "--ulimit", f"fsize=1572864",                                                                   # 최대 파일 크기 1.5MB로 제한

        "--memory", f"{test_case_memory_limit_mb}m",                                                    # 메모리 제한 (컨테이너 유지 비용, time/perf 실행 비용, tmpfs 유지 비용을 고려, 여유분 16mb 추가 할당), 내부 하위 프로세스는 메모리 사용 초과 시 SIGKILL 처리 되어 -9 반환하고 종료됨
        "--memory-swap", f"{test_case_memory_limit_mb}m",                                               # 메모리 제한을 정확하게 적용하기 위해 메모리 스왑 (디스크 할당) 금지
        "--cpus", f"{cpu_core_limit}",                                                                  # CPU 코어 수 제한 (서버 사양에 따라 여유가 있다면 1로 설정해도 괜찮음)
        "--pids-limit", f"{pids_limit}",                                                                # 프로세스 수 제한

        "--network", "none",                                                                            # 네트워크 차단
        "--cap-drop", "ALL",                                                                            # 기본적으로 부여되는 모든 권한을 제거하고, 최소한의 권한만 사용하도록 설정
        "--security-opt", "no-new-privileges",                                                          # 새로운 권한 획득 제한
        "--security-opt", f"seccomp={seccomp_profile_path}",                                            # 내부 시스템콜 제한

        "--workdir", f"/tmp",                                                                           # WORKDIR 설정, 모든 명령어 실행 루트
        "--init",                                                                                       # 좀비 프로세스가 생성되는 것을 방지하기 위해 init 프로세스를 컨테이너 내부 최상단 프로세스로 생성

        f"{sandbox_image}",                                                                             # 도커 이미지 설정

        # 컨테이너로 전달할 추가 시스템 argument
        f"/tmp/run.sh",
        json.dumps(test_cases),                                                                         # 테스트 케이스 입력 값 리스트 (JSON 직렬화)
        str(test_case_time_limit_sec),                                                                  # 테스트 케이스 실행 시간 제한
        str(test_case_memory_limit_mb)                                                                  # 테스트 케이스 메모리 상한
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
    """Docker 컨테이너 출력을 비동기적으로 처리하는 함수

    컨테이너 내부 스트림 출력을 파싱하고 결과를 웹훅으로 전송합니다.

    Args:
        stream (StreamReader): asyncio 스트림 리더 (stdout 또는 stderr)
        proc (Process): 실행 중인 도커 프로세스
        cleanup_job_and_return_event (Event): 작업 정리 이벤트
        job_id (str): 작업 ID
        verdicts (list[Verdict]): 결과를 저장할 Verdict 객체 리스트
        webhook_manager (AsyncWebhookManager): 웹훅 매니저
        tasks (list[Task]): 웹훅 응답 처리 작업 리스트

    Returns:
        None
    """
    unexpected_output = []
    try:
        while True:
            line = await stream.readline()
            if not line:
                break

            line_str = line.decode('utf-8').strip()
            if not line_str:
                continue

            try:
                result = json.loads(line_str)

                # JSON 이지만 dict가 아닌 단순 정수형 데이터 등인 경우는 알 수 없는 출력 처리
                if not isinstance(result, dict):
                    unexpected_output.append(line_str)
                    continue

                status = result.get('status')
                passed = result.get('passed')

                # 시스템 에러, 런타임/컴파일 에러 처리
                if status == 'system_error':
                    raise Exception(result.get('error'))

                elif status == 'compile_error':
                    verdict = Verdict(
                        passed=False,
                        compile_error=result.get('error')
                    )
                    verdicts.append(verdict)

                    webhook_event = TestCaseResult(job_id, verdict)
                    future = asyncio.ensure_future(webhook_manager.send_webhook(webhook_event))
                    tasks.append(asyncio.create_task(
                        handle_webhook_response(future, proc, cleanup_job_and_return_event, job_id)))

                elif status == 'runtime_error':
                    verdict = Verdict(
                        test_case_index=result.get('testCaseIndex'),
                        passed=False,
                        runtime_error=result.get('error')
                    )
                    verdicts.append(verdict)

                    webhook_event = TestCaseResult(job_id, verdict)
                    future = asyncio.ensure_future(webhook_manager.send_webhook(webhook_event))
                    tasks.append(asyncio.create_task(
                        handle_webhook_response(future, proc, cleanup_job_and_return_event, job_id)))

                elif isinstance(passed, bool):
                    verdict = Verdict(
                        test_case_index=result.get('testCaseIndex'),
                        passed=result.get('passed'),
                        elapsed_time_ms=result.get('elapsedTimeMs'),
                        memory_usage_mb=result.get('memoryUsageMb')
                    )
                    verdicts.append(verdict)

                    webhook_event = TestCaseResult(job_id, verdict)
                    future = asyncio.ensure_future(webhook_manager.send_webhook(webhook_event))
                    tasks.append(asyncio.create_task(
                        handle_webhook_response(future, proc, cleanup_job_and_return_event, job_id)))

                else:
                    unexpected_output.append(line_str)

                logging.info(f"[DEBUG] {result}")
            except json.JSONDecodeError:
                # JSON이 아닌 경우 예상치 못한 출력으로 간주
                unexpected_output.append(line_str)

        if unexpected_output:
            raise Exception(f"Unexpected output from container: {("\n".join(unexpected_output))}")

    except Exception:
        logging.error(f"Unexpected error occurred during handling job sandbox for job {job_id}", exc_info=True)

        proc.kill()
        cleanup_job_and_return_event.set()
        await webhook_manager.send_webhook(Error(job_id))


async def async_execute_code(user_id: int, job: Job, webhook_manager: AsyncWebhookManager):
    try:
        # 고유한 임시 디렉토리 생성 및 코드 파일 생성, with 블록을 벗어나면 내부 리소스 자동 제거
        with tempfile.TemporaryDirectory() as tmp_dir:
            # 소스 코드 임시 파일 생성
            code_decoded = base64.b64decode(job.code).decode("utf-8")
            test_cases = TEST_CASES[str(job.challenge_id)]
            code_file_name = CODE_FILE_NAME.get(job.code_language)

            tmp_code_path = os.path.join(tmp_dir, f"{code_file_name}")
            with open(tmp_code_path, "w", encoding="utf-8") as f:
                f.write(code_decoded)

            test_case_memory_limit = TEST_CASES_MEM_LIMITS[str(job.challenge_id)] + TEST_CASE_LIMITS_MEMORY_BONUS[job.code_language]
            test_case_time_limit = TEST_CASES_TIME_LIMITS[str(job.challenge_id)] + TEST_CASE_LIMITS_TIME_BONUS[job.code_language]

            # Docker 명령어 생성
            docker_cmd = _build_docker_run_cmd(
                tmp_code_path,
                job.code_language,
                random.sample(test_cases, len(test_cases)),
                test_case_memory_limit,
                test_case_time_limit
            )

            # 비동기 서브프로세스로 sandbox 실행
            sandbox_proc = await asyncio.create_subprocess_exec(
                *docker_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            tasks = []
            verdicts = []
            cleanup_job_and_return_event = asyncio.Event()

            # sandbox 출력 처리는 백그라운드 작업 실행
            # asyncio에 의해 자동으로 스케줄링
            stdout_task = asyncio.create_task(
                async_handle_output(sandbox_proc.stdout, sandbox_proc, cleanup_job_and_return_event, job.job_id, verdicts, webhook_manager, tasks)
            )
            stderr_task = asyncio.create_task(
                async_handle_output(sandbox_proc.stderr, sandbox_proc, cleanup_job_and_return_event, job.job_id, verdicts, webhook_manager, tasks)
            )

            tasks.append(stdout_task)
            tasks.append(stderr_task)

            # sandbox 타임아웃 설정
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

            judgment = create_judgment_from_verdicts(
                user_id=user_id,
                job_id=job.job_id,
                challenge_id=job.challenge_id,
                code_language=job.code_language,
                code=job.code,
                code_byte_size=len(job.code),
                submitted_at=job.submitted_at,
                verdicts=verdicts
            )

            await webhook_manager.send_webhook(judgment)
            job_repository.delete(job.job_id, user_id)

    # finally는 os._exit(code)를 호출하는 경우(os.exit(code)와 다름)를 제외하고 항상 실행 됨
    finally:
        await webhook_manager.shutdown()
        # asyncio의 이벤트 루프가 프로세스 종료 시(sandbox_proc.returncode가 설정된 후),
        # 내부적으로 파이프(sandbox_proc.stdout, sandbox_proc.stderr)는 자동으로 close
        # 만약 subprocess.Popen를 직접 사용하는 경우, pipe 수명 관리를 직접 해야함
        # TemporaryDirectory는 with 블록 벗어나면서 tmp_dir 이하 자원을 자동 정리