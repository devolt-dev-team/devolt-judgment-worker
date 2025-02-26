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
    elapsed_time_ms: int=None,
    runtime_error: str=None,
    compile_error: str=None
):
    message_dict = {
        "passed": passed,
        "testCaseIndex": test_case_index,
        "memoryUsedMb": memory_used_mb,
        "elapsedTimeMs": elapsed_time_ms,
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


def parse_elapsed_time(time_str: str) -> float:
    """
    "Elapsed (wall clock) time" 문자열을 초 단위의 float 값으로 변환합니다.
    예상되는 형식:
      - h:mm:ss.cc 또는 m:ss.cc (콜론이 포함된 경우)
      - 또는 초 단위의 숫자 (예: "00.11")
    """
    time_str = time_str.strip()

    # 콜론이 없으면 단순히 초 단위의 숫자로 변환
    if ":" not in time_str:
        return float(time_str)

    parts = time_str.split(':')

    # 형식: m:ss.cc
    if len(parts) == 2:
        minutes = int(parts[0])
        seconds = float(parts[1])
        return minutes * 60 + seconds

    # 형식: h:mm:ss.cc
    elif len(parts) == 3:
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = float(parts[2])
        return hours * 3600 + minutes * 60 + seconds
    else:
        print_system_error(
            f"Unknown elapsed time format: {time_str}",
            return_code=1
        )


# java 컴파일 시간 제한은 실행 시간 제한과 별도로 적정하게 설정할 것
def compile_java_code(java_filename: str, test_case_memory_limit: int, compile_time_limit: float = 5.0):
    # xms: 초기 힙 사이즈, xmx: 최대 힙 사이즈, xss: 스레드 스택 사이즈 (보통 기본 1mb)
    compile_cmd = ["javac", f"-J-Xms{int(test_case_memory_limit / 4)}m", f"-J-Xmx{test_case_memory_limit}m", "-J-Xss512k", "-encoding", "UTF-8", java_filename]
    try:
        # 서브 프로세스 동기적 실행(subprocess.run)
        # 다음 라인으로 넘어가면 서브 프로세스는 종료된 상태임
        proc_compile = subprocess.run(compile_cmd, capture_output=True, text=True, timeout=compile_time_limit)
        if proc_compile.returncode != 0:
            if proc_compile.returncode == -9 or "Killed" in proc_compile.stderr:
                print_verdict(
                    False,
                    compile_error="컴파일 메모리 제한 초과"
                )
            else:
                print_verdict(
                    False,
                    compile_error=proc_compile.stderr.rstrip()
                )
    except subprocess.TimeoutExpired:
        print_verdict(
            False,
            compile_error=f"컴파일 시간 제한 초과"
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

        execute_cmd = [
            "/usr/bin/time", "-v", "-o", "time_output.txt",     # /usr/bin/time 유틸리티를 사용하여 실행하는 프로세스의 리소스 사용 통계를 얻음
            "java",
            f"-Xms{test_case_memory_limit // 4}m",              # 최초 힙 메모리 지정
            f"-Xmx{test_case_memory_limit}m",                   # 최대 힙 메모리 지정
            "-Xss512k",                                         # thread stack 최대 size 지정
            "-Dfile.encoding=UTF-8",
            "-XX:+UseSerialGC",                                 # 예측 가능한 성능과 낮은 GC 오버헤드를 위해 Serial GC 옵션을 사용하여 단일 스레드 GC 설정, openJDK 17은 64비트 Linux 환경에서 JVM이 Server 모드로 동작하며, GC는 멀티 스레드 방식이 default
            "Main"
        ]

        try:
            # 서브 프로세스 동기적 실행(subprocess.run)
            # 다음 라인으로 넘어가면 서브 프로세스는 종료된 상태임
            proc_run = subprocess.run(execute_cmd, input=input_str, capture_output=True, text=True, timeout=test_case_time_limit)

            if proc_run.returncode != 0:
                if "/usr/bin/time" in proc_run.stderr:
                    print_system_error(
                        f"Unexpected exception occurred during execution: {proc_run.stderr.rstrip()}",
                        return_code=1
                    )
                else:
                    # 힙 메모리 제한 초과 시 java.lang.OutOfMemoryError 발생하므로
                    # 별도로 메모리 초과 케이스를 조건문으로 필터링 하지 않아도 OK
                    print_verdict(
                        False,
                        test_case_index=idx+1,
                        runtime_error=proc_run.stderr.rstrip()
                    )
                continue
        except subprocess.TimeoutExpired:
            print_verdict(
                False,
                test_case_index=idx+1,
                runtime_error="실행 시간 제한 초과"
            )
            continue
        except Exception as e:
            print_system_error(
                f"Unexpected exception occurred during execution: {str(e)}",
                return_code=1
            )

        user_code_output = proc_run.stdout.rstrip()

        # time 유틸의 출력에서 메모리 사용량과 실행 시간 기록 파싱
        mem_used_kb = None
        elapsed_time_sec = None
        try:
            with open("time_output.txt", "r") as f:
                for line in f:
                    if "Maximum resident set size" in line:
                        parts = line.split(":", 1)
                        if len(parts) > 1:
                            mem_used_kb = int(parts[1].strip())
                    if "Elapsed (wall clock) time" in line:
                        parts = line.rsplit(":", 1)
                        if len(parts) > 1:
                            elapsed_time_sec = parse_elapsed_time(parts[1].strip())

            if mem_used_kb is None or elapsed_time_sec is None:
                raise ValueError("Failed to read execution log from time_output.txt")
        except Exception as e:
            print_system_error(
                f"Error reading time output file: {str(e)}",
                return_code=1
            )

        print_verdict(
            passed=(user_code_output == expected_result),
            test_case_index=idx + 1,
            memory_used_mb=round(mem_used_kb / 1024.0, 2),
            elapsed_time_ms=round(elapsed_time_sec * 1000 if elapsed_time_sec <= test_case_time_limit else test_case_time_limit * 1000)
        )


def process_arguments():
    # sys.argv[0] : 현재 실행 중인 스크립트 경로
    # sys.argv[1] : 마운트 경로
    # sys.argv[2] : JSON 직렬화된 테스트 케이스 입력 과 기댓 값 리스트
    # sys.argv[3] : 각 테스트 케이스 실행 시점 힙 메모리 사용량 상한 (mb 단위, int로 변환 필요)
    # sys.argv[4] : 각 테스트 케이스 실행에 적용할 시간 제한 (초 단위, float로 변환 필요)

    # 1) 매개변수 개수 확인
    if len(sys.argv) != 5:
        print_system_error(
            "Insufficient arguments provided",
            return_code=1
        )

    # 2) code(파일) 파싱: 마운트된 코드 파일을 읽어서 처리
    try:
        with open("/tmp/code", "r", encoding="utf-8") as f:
            code = f.read()
    except Exception as e:
        print_system_error(
            f"File read error: {str(e)}",
            return_code=1
        )

    # 3) 마운트 경로로 이동
    try:
        os.chdir(sys.argv[1])
    except Exception as e:
        print_system_error(
            f"Changing directory failed: {str(e)}",
            return_code=1
        )

    # 4) 테스트 케이스 파싱
    try:
        test_cases = json.loads(sys.argv[2])
    except Exception as e:
        print_system_error(
            f"JSON parse error: {str(e)}",
            return_code=1
        )

    # 5) 테스트 케이스 메모리 상한 파싱
    try:
        test_case_memory_limit = int(sys.argv[3])
        if test_case_memory_limit <= 0:
            raise ValueError("Test case memory limit value must be > 0")
    except Exception as e:
        print_system_error(
            f"Memory limit parse error: {str(e)}",
            return_code=1
        )

    # 6) 테스트 케이스 실행 시간 제한 파싱
    try:
        test_case_time_limit = float(sys.argv[4])
        if test_case_time_limit <= 0:
            raise ValueError("Test case time limit value must be > 0")
    except Exception as e:
        print_system_error(
            f"Time limit parse error: {str(e)}",
            return_code=1
        )

    # 7) 자바 파일 생성
    try:
        java_filename = "Main.java"
        with open(java_filename, "w", encoding="utf-8") as f:
            f.write(code)
    except Exception as e:
        print_system_error(
            f"File write error: {str(e)}",
            return_code=1
        )

    return java_filename, test_case_memory_limit, test_cases, test_case_time_limit


def main():
    java_filename, test_case_memory_limit, test_cases, test_case_time_limit = process_arguments()
    compile_java_code(java_filename, test_case_memory_limit)
    execute_with_test_cases(test_cases, test_case_memory_limit, test_case_time_limit)


if __name__ == "__main__":
    main()