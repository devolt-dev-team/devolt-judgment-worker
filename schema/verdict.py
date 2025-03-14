from dataclasses import dataclass
from typing import Optional

from schema import Schema


@dataclass
class Verdict(Schema):
    passed: bool
    test_case_index: Optional[int] = None
    memory_usage_mb: Optional[float] = None
    elapsed_time_ms: Optional[int] = None
    runtime_error: Optional[str] = None
    compile_error: Optional[str] = None


# dict -> schema 변환 테스트: dict 필드 검증 및 인스턴스 반환
if __name__=='__main__':
    input_dict = {
        "passed": True,
        "testCaseIndex": 1,
        "memoryUsageMb": 15.2,
        "elapsedTimeMs": 54,
        "runtimeError": None,
        "compileError": None
    }

    verdict = Verdict.create_from_dict(input_dict)
    print(verdict)
