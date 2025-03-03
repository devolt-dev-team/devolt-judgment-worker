import os
import sys
import subprocess
import json


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


def parse_python_compile_error_message(stderr: str):
    lines = stderr.split("\n")
    error_message = None
    for i, line in enumerate(lines):
        if "py_compile.PyCompileError:" in line:
            # "py_compile.PyCompileError:" 이후 첫 번째 공백이 아닌 문자 찾기
            extracted_message_in_curr_line = line.split("py_compile.PyCompileError:", 1)[1].strip()
            if extracted_message_in_curr_line:
                error_message = extracted_message_in_curr_line + "\n" + "\n".join(lines[i + 1:]).strip()
            else:
                error_message = "\n".join(lines[i + 1:]).strip()
            break

    return error_message


# 일반적으로 python은 실행 시 컴파일과 실행이 동시에 이루어지고, 이를 별도로 실행하진 않지만
# 코딩 테스트 채점을 위해 컴파일 과정 분리
# python 컴파일 시간 제한은 실행 시간 제한과 별도로 적정하게 설정할 것
def compile_python_code(compile_time_limit: float=5.0):
    compile_cmd = [
        "python3",
        "-c",
        "import py_compile; py_compile.compile(r'main.py', doraise=True)"  # 컴파일 에러 발생 시 예외를 발생, subprocess가 비정상 종료 유도
    ]
    try:
        # 서브 프로세스 동기적 실행(subprocess.run)
        # 다음 라인으로 넘어가면 서브 프로세스는 종료된 상태임
        proc_compile = subprocess.run(
            compile_cmd,
            capture_output=True,
            text=True,
            timeout=compile_time_limit,
            encoding='utf-8',
            errors='replace',
        )
        if proc_compile.returncode != 0:
            # 힙 메모리 제한 초과 케이스의 경우, Python 내부적으로 MemoryError를 발생시켜 처리하므로 JS 처럼 별도의 stderr 분석은 필요 없음
            # 내부 로직에서 메모리 할당 실패로 인한 Segmentation Fault이 발생한 경우 : -11 or 139
            # 컨테이너 메모리 상한 초과로 인해 SIGKILL이 호출되어 강제로 종료될 경우 : -9
            if proc_compile.returncode == -9 or proc_compile.returncode == -11 or proc_compile.returncode == 137 or "Killed" in proc_compile.stderr:
                compile_error_message = "컴파일 메모리 사용량 최대 허용 한도 초과"
            else:
                compile_error_message = parse_python_compile_error_message(proc_compile.stderr)
            print_verdict(
                False,
                compile_error=compile_error_message
            )
    except subprocess.TimeoutExpired:
        print_verdict(
            False,
            compile_error=f"컴파일 실행 시간 최대 허용 한도 초과"
        )
    except Exception as ex:
        print_system_error(
            f"Unexpected exception occurred during compilation: {str(ex)}",
            return_code=1
        )


def execute_with_test_cases(test_cases: list, test_case_memory_limit: int, test_case_time_limit: float):
    for idx, tc in enumerate(test_cases):
        inputs: list[str] = tc[0]
        expected_result: str = tc[1]
        input_str: str = "\n".join(inputs)
        time_output_file_name = f"time_output{idx + 1}.txt"

        execute_cmd = [
            "/usr/bin/time", "-f", "%e %M", "-o", time_output_file_name,    # /usr/bin/time 유틸리티를 사용하여 실행하는 프로세스의 리소스 사용 통계를 얻음
            "python3",
            "main.py"
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
                    if proc_run.returncode == -9 or proc_run.returncode == -11 or proc_run.returncode == 137 or "Killed" in proc_run.stderr:
                        runtime_error_message = "런타임 메모리 사용량 최대 허용 한도 초과"
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
                runtime_error=f"런타임 실행 시간 통과 기준 {test_case_time_limit}초 초과"
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

        # 메모리 제한 초과 체크 및 결과 출력
        memory_used_mb = round(mem_used_kb / 1024.0, 2)
        if memory_used_mb > test_case_memory_limit:
            print_verdict(
                False,
                test_case_index=idx + 1,
                runtime_error=f"런타임 메모리 사용량 통과 기준 {test_case_memory_limit}mb 초과"
            )
        else:
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

    # 7) 파이썬 파일 생성
    try:
        with open("main.py", "w", encoding="utf-8") as f:
            f.write(code)
    except Exception as e:
        print_system_error(
            f"File write error: {str(e)}",
            return_code=1
        )

    return test_case_memory_limit, test_cases, test_case_time_limit


def main():
    test_case_memory_limit, test_cases, test_case_time_limit = process_arguments()
    compile_python_code()
    execute_with_test_cases(test_cases, test_case_memory_limit, test_case_time_limit)


if __name__ == "__main__":
    main()