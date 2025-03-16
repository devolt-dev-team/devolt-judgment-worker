from dataclasses import dataclass
from enum import Enum
from typing import Optional

from schema import Schema, Verdict


class UnpassedReason(Enum):
    """실패 원인을 나타내는 열거형"""
    COMPILE_ERROR = "COMPILE_ERROR"
    RUNTIME_ERROR = "RUNTIME_ERROR"
    WRONG_ANSWER = "WRONG_ANSWER"

@dataclass
class Judgment(Schema):
    """코드 채점의 최종 결과를 나타내는 기반 데이터 클래스 (DB 저장용)"""
    user_id: int
    job_id: str
    challenge_id: int
    code_language: str
    code: str
    code_byte_size: int
    submitted_at: str

@dataclass
class PassedJudgment(Judgment):
    """모든 테스트 케이스가 통과한 채점 결과"""
    max_memory_usage_mb: float
    max_elapsed_time_ms: int

@dataclass
class UnpassedJudgment(Judgment):
    """하나 이상의 테스트 케이스가 실패하거나 컴파일/런타임 에러가 발생한 채점 결과"""
    unpassed_reason: UnpassedReason
    detail: Optional[str] = None

def create_judgment_from_verdicts(
    verdicts: list[Verdict],
    user_id: int,
    job_id: str,
    challenge_id: int,
    code_language: str,
    code: str,
    code_byte_size: int,
    submitted_at: str
) -> Judgment:
    """
    List[Verdict]로부터 적절한 Judgment 하위 클래스 인스턴스를 생성하는 팩토리 메서드.

    Args:
        verdicts: Verdict 객체 리스트 (채점 결과 데이터).
        user_id, job_id, challenge_id, code_language, code, code_byte_size, submitted_at:
            Judgment 공통 필드 값.

    Returns:
        Judgment: PassedJudgment 또는 UnpassedJudgment 인스턴스.
    """
    # 공통 필드 준비
    base_kwargs = {
        "user_id": user_id,
        "job_id": job_id,
        "challenge_id": challenge_id,
        "code_language": code_language,
        "code": code,
        "code_byte_size": code_byte_size,
        "submitted_at": submitted_at
    }

    # 컴파일 에러 확인
    for verdict in verdicts:
        if verdict.compile_error is not None:
            return UnpassedJudgment(
                **base_kwargs,
                unpassed_reason=UnpassedReason.COMPILE_ERROR,
                detail=verdict.compile_error  # 첫 번째 컴파일 에러 메시지를 상세 정보로 저장
            )

    # 런타임 에러 확인
    for verdict in verdicts:
        if verdict.runtime_error is not None:
            return UnpassedJudgment(
                **base_kwargs,
                unpassed_reason=UnpassedReason.RUNTIME_ERROR,
                detail=verdict.runtime_error  # 첫 번째 런타임 에러 메시지를 상세 정보로 저장
            )

    # 오답 확인
    all_passed = True
    for verdict in verdicts:
        if not verdict.passed:
            all_passed = False
            break

    if not all_passed:
        # 오답이 있는 경우
        return UnpassedJudgment(
            **base_kwargs,
            unpassed_reason=UnpassedReason.WRONG_ANSWER,
            detail=None  # 오답의 경우 특별한 상세 정보는 없음
        )
    else:
        # 모든 테스트가 통과한 경우 PassedJudgment 반환
        max_memory_usage_mb = 0.0
        max_elapsed_time_ms = 0

        for verdict in verdicts:
            if verdict.memory_usage_mb is None or verdict.elapsed_time_ms is None:
                raise ValueError(
                    "Invalid Verdict: All verdicts must provide memory_usage_mb and elapsed_time_ms for PassedJudgment."
                )
            max_memory_usage_mb = max(max_memory_usage_mb, verdict.memory_usage_mb)
            max_elapsed_time_ms = max(max_elapsed_time_ms, verdict.elapsed_time_ms)

        return PassedJudgment(
            **base_kwargs,
            max_memory_usage_mb=max_memory_usage_mb,
            max_elapsed_time_ms=max_elapsed_time_ms
        )


if __name__ == "__main__":
    # 공통 데이터
    common_args = {
        "user_id": 1,
        "job_id": "job123",
        "challenge_id": 42,
        "code_language": "c11",
        "code": "int main() { return 0; }",
        "code_byte_size": 20,
        "submitted_at": "2025-03-15T10:00:00"
    }

    # 컴파일 에러 사례
    verdicts1 = [Verdict(passed=False, compile_error="syntax error")]
    result1 = create_judgment_from_verdicts(verdicts1, **common_args)
    print(result1)
    print(result1.as_dict())

    # 런타임 에러 사례
    verdicts2 = [
        Verdict(passed=True, test_case_index=1, memory_usage_mb=1.5, elapsed_time_ms=50),
        Verdict(passed=False, test_case_index=2, runtime_error="segmentation fault")
    ]
    result2 = create_judgment_from_verdicts(verdicts2, **common_args)
    print(result2)
    print(result2.as_dict())

    # 정상 실행 사례
    verdicts3 = [
        Verdict(passed=True, test_case_index=1, memory_usage_mb=1.5, elapsed_time_ms=50),
        Verdict(passed=True, test_case_index=2, memory_usage_mb=2.0, elapsed_time_ms=60)
    ]
    result3 = create_judgment_from_verdicts(verdicts3, **common_args)
    print(result3)
    print(result3.as_dict())

    # 일부 실패 사례
    verdicts4 = [
        Verdict(passed=True, test_case_index=1, memory_usage_mb=1.5, elapsed_time_ms=50),
        Verdict(passed=False, test_case_index=2, memory_usage_mb=2.0, elapsed_time_ms=60)
    ]
    result4 = create_judgment_from_verdicts(verdicts4, **common_args)
    print(result4)
    print(result4.as_dict())
