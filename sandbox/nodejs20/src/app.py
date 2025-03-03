import os
import sys
import subprocess
import json
import ast


# 테스트 케이스 채점 결과 출력
# 컴파일 에러의 경우 프로세스 실행 종료
def print_verdict(
    passed: bool,
    test_case_index: int=None,
    memory_used_mb: float=None,
    elapsed_time_sec: float=None,
    runtime_error: str=None,
    compile_error: str=None
):
    message_dict = {
        "passed": passed,
        "testCaseIndex": test_case_index,
        "memoryUsedMb": memory_used_mb,
        "elapsedTimeSec": elapsed_time_sec,
        "runtimeError": runtime_error,
        "compileError": compile_error
    }
    print(f"VERDICT:{json.dumps(message_dict)}")

    # 에러 발생시 채점 중단 후 failed 처리
    if compile_error is not None or runtime_error is not None or not passed:
        sys.exit(0)


# 에러 출력 후 프로세스 실행 종료
def print_system_error(system_error: str, return_code: int=1):
    message_dict = {
        "error": system_error
    }
    print(f"SYSTEM_ERROR:{json.dumps(message_dict)}")
    sys.exit(return_code)


def parse_time_output(time_output_file_name: str) -> tuple[float, int]:
    try:
        with open(time_output_file_name, "r", encoding="utf-8") as f:
            output_line = f.read().strip()  # 예: "1.23 56789"
            parts = output_line.split()
            if len(parts) != 2:
                raise ValueError("Unexpected time output format")
            elapsed_time_sec = float(parts[0])
            mem_used_kb = int(parts[1])

        return elapsed_time_sec, mem_used_kb
    except Exception as e:
        print_system_error(
            f"Error reading time output file: {str(e)}",
            return_code=1
        )


def get_file_extension(filename: str) -> str:
    """
        파일명에서 확장자를 추출합니다.

        Args:
            filename (str): 파일 경로 또는 파일명 (예: "/tmp/tmp123.java", "main.js").

        Returns:
            str: 파일 확장자 (예: ".java", ".js"). 확장자가 없으면 빈 문자열 ("") 반환.
        """
    _, extension = os.path.splitext(filename)
    return extension.lower()  # 소문자로 변환하여 일관성 유지


def execute_with_test_cases(test_cases: list, test_case_memory_limit: int, test_case_time_limit: float, javascript_filename: str):
    for idx, tc in enumerate(test_cases):
        inputs: list[str] = tc[0]
        expected_result: str = tc[1]
        input_str: str = "\n".join(inputs)
        time_output_file_name = f"time_output{idx + 1}.txt"

        execute_cmd = [
            "/usr/bin/time", "-f", "%e %M", "-o", time_output_file_name,    # /usr/bin/time 유틸리티를 사용하여 실행하는 프로세스의 리소스 사용 통계를 얻음
            "node",
            f"--max-old-space-size={test_case_memory_limit}",               # 최대 힙 메모리 지정
            "--stack-size=1024",                                            # stack 최대 size 지정
            javascript_filename
        ]

        try:
            # 서브 프로세스 동기적 실행(subprocess.run)
            # 다음 라인으로 넘어가면 서브 프로세스는 종료된 상태임
            proc_run = subprocess.run(
                execute_cmd,
                input=input_str,
                capture_output=True,
                text=True,
                timeout=test_case_time_limit,
                encoding='utf-8',
                errors='replace'
            )

            if proc_run.returncode != 0:
                if "/usr/bin/time" in proc_run.stderr:
                    print_system_error(
                        f"Unexpected exception occurred during execution: {proc_run.stderr.rstrip()}",
                        return_code=1
                    )
                else:
                    # 힙 메모리 제한 초과 시 JavaScript heap out of memory 발생하므로
                    # 별도로 메모리 초과 케이스를 조건문으로 필터링 하지 않아도 OK
                    if "JavaScript heap out of memory" in proc_run.stderr:
                        runtime_error_message = "JavaScript heap out of memory"
                    else:
                        runtime_error_message = proc_run.stderr.rstrip()
                    print_verdict(
                        False,
                        test_case_index=idx+1,
                        runtime_error=runtime_error_message
                    )
                continue
        except subprocess.TimeoutExpired:
            print_verdict(
                False,
                test_case_index=idx+1,
                runtime_error=f"실행 시간 제한 {test_case_time_limit}초 초과"
            )
            continue
        except Exception as e:
            print_system_error(
                f"Unexpected exception occurred during execution: {str(e)}",
                return_code=1
            )

        user_code_output = proc_run.stdout.rstrip()

        # time 유틸의 출력에서 메모리 사용량과 실행 시간 기록 파싱
        elapsed_time_sec, mem_used_kb = parse_time_output(time_output_file_name)

        print_verdict(
            passed=(user_code_output == expected_result),
            test_case_index=idx + 1,
            memory_used_mb=round(mem_used_kb / 1024.0, 2),
            elapsed_time_sec=elapsed_time_sec if elapsed_time_sec <= test_case_time_limit else test_case_time_limit
        )


def process_arguments():
    # sys.argv[0] : 현재 실행 중인 파이썬 모듈 경로
    # sys.argv[1] : 임시 코드 파일명
    # sys.argv[2] : tmpfs 마운트 경로
    # sys.argv[3] : JSON 직렬화된 테스트 케이스 입력 과 기댓 값 리스트
    # sys.argv[4] : 각 테스트 케이스 실행 시점 힙 메모리 사용량 상한 (mb 단위, int로 변환 필요)
    # sys.argv[5] : 각 테스트 케이스 실행에 적용할 시간 제한 (초 단위, float로 변환 필요)

    # 1) 매개변수 개수 확인
    if len(sys.argv) != 6:
        print_system_error(
            "Insufficient arguments provided",
            return_code=1
        )

    # 2) code(파일) 파싱: 마운트된 코드 파일을 읽어서 처리
    try:
        code_filename = sys.argv[1]
        with open(f"/tmp/{code_filename}", "r", encoding="utf-8") as f:
            code = f.read()
    except Exception as e:
        print_system_error(
            f"File read error: {str(e)}",
            return_code=1
        )

    # 3) tmpfs 마운트 경로로 이동
    try:
        os.chdir(sys.argv[2])
    except Exception as e:
        print_system_error(
            f"Changing directory failed: {str(e)}",
            return_code=1
        )

    # 4) 테스트 케이스 파싱
    try:
        test_cases = json.loads(sys.argv[3])
    except Exception as e:
        print_system_error(
            f"JSON parse error: {str(e)}",
            return_code=1
        )

    # 5) 테스트 케이스 메모리 상한 파싱
    try:
        test_case_memory_limit = int(sys.argv[4])
        if test_case_memory_limit <= 0:
            raise ValueError("Test case memory limit value must be > 0")
    except Exception as e:
        print_system_error(
            f"Memory limit parse error: {str(e)}",
            return_code=1
        )

    # 6) 테스트 케이스 실행 시간 제한 파싱
    try:
        test_case_time_limit = float(sys.argv[5])
        if test_case_time_limit <= 0:
            raise ValueError("Test case time limit value must be > 0")
    except Exception as e:
        print_system_error(
            f"Time limit parse error: {str(e)}",
            return_code=1
        )

    # 7) 자바스크립트 파일 생성
    try:
        javascript_filename = f"main{get_file_extension(code_filename)}"
        with open(javascript_filename, "w", encoding="utf-8") as f:
            f.write(code)
    except Exception as e:
        print_system_error(
            f"File write error: {str(e)}",
            return_code=1
        )

    return test_case_memory_limit, test_cases, test_case_time_limit, javascript_filename


def main():
    test_case_memory_limit, test_cases, test_case_time_limit, javascript_filename = process_arguments()
    execute_with_test_cases(test_cases, test_case_memory_limit, test_case_time_limit, javascript_filename)


if __name__ == "__main__":
    main()