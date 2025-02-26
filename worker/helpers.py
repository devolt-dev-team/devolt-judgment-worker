import random
import string
import json
import threading
import requests
from typing import IO
import logging

from config import WebhookConfig
from schema import Schema, Verdict
from schema.webhook_event import TestCaseResult, JobCancellation, Error, SubmissionResult
from schema.job import CodeChallengeJudgmentJob as Job
from redisutil.repository import job_repository


def create_random_string(length: int = 8) -> str:
    chars = string.ascii_lowercase + string.digits
    return ''.join(random.choice(chars) for _ in range(length))


def build_docker_run_cmd(
    tmp_code_path: str,
    docker_image_name: str,
    test_cases: tuple[tuple[list, str]],
    test_case_memory_limit_mb: int,
    test_case_time_limit_sec: float
) -> list[str]:
    tmpfs_path = f"/tmp/{create_random_string(length=16)}"

    # 사양에 따라 min 값을 1정도로 할당 해도 괜찮음
    # 문제에 따라 조정이 필요한 경우 다른 상수 값 처럼 문제 별로 설정한 값을 할당할 것
    test_case_cpu_core_limit: float = 0.5
    pids_limit = 300

    return [
        "docker", "run", "--rm", "-t",                                              # --rm: 컨테이너가 종료될 때 컨테이너와 관련된 리소스(파일 시스템, 볼륨) 제거, -t: 컨테이너 출력을 즉시 read하기 위해 컨테이너에 가상 TTY 할당하고 subprocess의 I/O 스트림과 직접 연결
        "--network", "none",                                                        # 네트워크 차단
        "--mount", f"type=bind,source={tmp_code_path},target=/tmp/code,readonly",   # 코드는 파일로 전달
        "--mount", f"type=tmpfs,destination={tmpfs_path}",                          # 컨테이너 내부에서 쓰기 가능한 마운트 경로 설정
        "--read-only",                                                              # 파일 시스템은 기본적으로 읽기 전용 설정
        "--memory", f"{test_case_memory_limit_mb + 64}m",                                   # 컨테이너 메모리 제한
        "--cpus", f"{test_case_cpu_core_limit}",                                    # CPU 코어 수 제한 (서버 사양에 따라 여유가 있다면 1로 설정해도 괜찮음)
        "--pids-limit", f"{pids_limit}",                                            # 프로세스 수 제한
        "--cap-drop", "ALL",                                                        # 기본적으로 부여되는 모든 권한을 제거하고, 최소한의 권한만 사용하도록 설정
        docker_image_name,                                                          # 도커 이미지 설정

        # Dockerfile에 설정된 ENTRYPOINT과 함께 전달할 argument 목록
        tmpfs_path,                                                                 # tmpfs 마운트 경로 전달
        json.dumps(test_cases),                                                     # 테스트 케이스 별 input, 정답을 유지하는 튜플 JSON 직렬화
        str(test_case_memory_limit_mb),                                             # 테스트 케이스 메모리 제한
        str(test_case_time_limit_sec)                                               # 테스트 케이스 실행 시간 제한
    ]


def send_webhook(webhook_event_schema: Schema):
    try:
        if type(webhook_event_schema) is TestCaseResult:
            endpoint = WebhookConfig.WEBHOOK_NOTIFY_VERDICT_ENDPOINT
        elif type(webhook_event_schema) is SubmissionResult:
            endpoint = WebhookConfig.WEBHOOK_NOTIFY_SUBMISSION_RESULT_ENDPOINT
        else:
            endpoint = WebhookConfig.WEBHOOK_NOTIFY_ERROR_ENDPOINT

        headers = {'Content-Type': 'application/json'}
        response = requests.post(endpoint, json=webhook_event_schema.as_dict(), headers=headers, timeout=10)

        # HTTP 관련 에러 발생 시 예외 raise
        response.raise_for_status()

        return response.status_code
    except requests.exceptions.RequestException as e:
        return getattr(e.response, "status_code", 500)


def handle_output(
    pipe: IO,
    pipe_name: str,
    sandbox_proc,
    cleanup_job_event: threading.Event,
    user_id: int,
    job_id: str,
    verdicts: list[Verdict],
):
    try:
        # pipe.readline()은 동기 호출로 동작, 새로운 출력이 pipe에 추가될 때 까지 대기
        for line in iter(pipe.readline, ''):
            last_job_data = job_repository.find_by_user_id_and_job_id(user_id, job_id)
            if not last_job_data:
                sandbox_proc.kill()

                logging.error(f"[{job_id} 작업이 실행 중 만료되었습니다.]")
                send_webhook(Error(job_id, "작업이 만료되었습니다"))
                break

            if last_job_data.stop_flag:
                sandbox_proc.kill()
                cleanup_job_event.set()

                logging.info(f'[{job_id} 작업을 중단합니다.]')
                send_webhook(JobCancellation(job_id))
                break

            if line and line.startswith("VERDICT:"):
                verdict = Verdict.create_from_dict(json.loads(line[len("VERDICT:"):]))
                verdicts.append(verdict)

                updated_job = job_repository.update(
                    job_id,
                    user_id,
                    last_test_case_index=verdict.test_case_index,
                    verdicts=verdicts
                )

                if updated_job == -1:
                    sandbox_proc.kill()

                    logging.error(f"[{job_id} 작업이 실행 중 만료되었습니다.]")
                    send_webhook(Error(job_id, "작업이 만료되었습니다"))
                    break
                elif updated_job == 0:
                    sandbox_proc.kill()
                    cleanup_job_event.set()

                    logging.error(f"[{job_id} 작업 정보 업데이트 과정에서 발생한 오류가 없지만 실제 작업은 업데이트 되지 않았습니다.]")
                    send_webhook(Error(job_id))
                    break

                response_code = send_webhook(TestCaseResult(job_id, verdict))
                if response_code != 200:
                    sandbox_proc.kill()
                    cleanup_job_event.set()

                    logging.info(f"[현재 {job_id} 작업 채점 결과를 수신할 수 있는 사용자가 없습니다. 작업이 잠시후 종료됩니다. 응답 코드: {response_code}]")
                    break

            elif line and line.startswith("SYSTEM_ERROR:"):
                system_error = (json.loads(line[len("SYSTEM_ERROR:"):]))["error"]
                logging.error(f"[{job_id} 작업 실행 중 하위 프로세스에서 치명적 오류가 발생했습니다. 오류: {system_error}]")

                # SYSTEM_ERROR 메시지 출력 후 해당 프로세스는 종료됨, sandbox_proc.kill()이 필요 없음
                cleanup_job_event.set()

                send_webhook(Error(job_id))
                break

            else:
                # 프로세스 실행 중 컨테이너 내부 코드 실행 파이썬 스크립트 외적인 요인으로 발생한 stderr 처리
                raise Exception(line.rstrip())
    except Exception as ex:
        sandbox_proc.kill()
        cleanup_job_event.set()

        logging.error(f"[{job_id} 작업 출력 처리 중 하위 스레드에서 처리되지 않은 예외 발생]", exc_info=True)
        send_webhook(Error(job_id))