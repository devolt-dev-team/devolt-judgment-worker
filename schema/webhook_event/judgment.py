from dataclasses import dataclass
from typing import Optional

from schema import Schema, Verdict
from common import CodeLanguage, FailureCause


@dataclass
class Judgment(Schema):
    """코드 채점의 최종 결과를 나타내는 기반 데이터 클래스 (DB 저장용)"""
    user_id: int
    job_id: str
    challenge_id: int
    passed: bool
    code_language: CodeLanguage
    code: str
    code_byte_size: int
    submitted_at: str

    def __post_init__(self):
        """객체 초기화 후 code_language를 문자열에서 CodeLanguage 객체로 변환"""
        if isinstance(self.code_language, str):
            self.failure_cause = CodeLanguage(self.code_language)

    @classmethod
    def create_from_dict(cls, judgment_dict: dict) -> "Judgment":
        """
        Description:
            부모 클래스 Schema의 create_from_dict를 호출한 뒤,
            code_language 필드를 CodeLanguage 객체로 변환하여 인스턴스를 생성합니다.

        Args:
            judgment_dict (dict): 입력 딕셔너리

        Returns:
            Judgment: 생성된 인스턴스
        """
        # 부모 클래스 Schema의 create_from_dict 호출
        instance = super().create_from_dict(judgment_dict)

        # code_language 변환 (문자열 -> CodeLanguage 객체)
        if isinstance(instance.code_language, str):
            instance.code_language = CodeLanguage(instance.code_language)

        return instance


@dataclass
class PassedJudgment(Judgment):
    """모든 테스트 케이스가 통과한 채점 결과"""
    max_memory_usage_mb: float
    max_elapsed_time_ms: int

@dataclass
class UnpassedJudgment(Judgment):
    """하나 이상의 테스트 케이스가 실패하거나 컴파일/런타임 에러가 발생한 채점 결과"""
    failure_cause: FailureCause
    failure_detail: Optional[str] = None

    def __post_init__(self):
        """객체 초기화 후 failure_cause를 문자열에서 FailureCause 객체로 변환"""
        if isinstance(self.failure_cause, str):
            self.failure_cause = FailureCause(self.failure_cause)

    @classmethod
    def create_from_dict(cls, unpassed_judgment_dict: dict) -> "UnpassedJudgment":
        """
        Description:
            부모 클래스 Judgment의 create_from_dict를 호출한 뒤,
            failure_cause 필드를 FailureCause 객체로 변환하여 인스턴스를 생성합니다.

        Args:
            unpassed_judgment_dict (dict): 입력 딕셔너리

        Returns:
            UnpassedJudgment: 생성된 인스턴스
        """
        # 부모 클래스 Judgment의 create_from_dict 호출
        instance = super().create_from_dict(unpassed_judgment_dict)

        # failure_cause 변환 (문자열 -> FailureCause 객체)
        if isinstance(instance.failure_cause, str):
            instance.failure_cause = FailureCause(instance.failure_cause)

        return instance

def create_judgment_from_verdicts(
    verdicts: list[Verdict],
    user_id: int,
    job_id: str,
    challenge_id: int,
    code_language: CodeLanguage,
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
        "passed": True,
        "code_language": code_language,
        "code": code,
        "code_byte_size": code_byte_size,
        "submitted_at": submitted_at
    }

    # 최대 메모리 사용량,
    max_memory_usage_mb = 0.0
    max_elapsed_time_ms = 0

    for verdict in verdicts:
        if not verdict.passed:
            if verdict.failure_cause is None:
                raise ValueError(
                    f"Invalid Verdict: Failure verdict at test case {verdict.test_case_index} has no failure cause."
                )

            base_kwargs.update({"passed": False})
            return UnpassedJudgment(
                **base_kwargs,
                failure_cause=verdict.failure_cause,
                failure_detail=verdict.failure_detail
            )

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
        "code_language": CodeLanguage.C11,
        "code": "int main() { return 0; }",
        "code_byte_size": 20,
        "submitted_at": "2025-03-15T10:00:00"
    }

    # 컴파일 에러 사례
    verdicts1 = [Verdict(passed=False, test_case_index=1, failure_cause=FailureCause.COMPILE_ERROR, failure_detail="syntax error")]
    result1 = create_judgment_from_verdicts(verdicts1, **common_args)
    print(result1)
    print(result1.as_dict())

    # 런타임 에러 사례
    verdicts2 = [
        Verdict(passed=True, test_case_index=1, memory_usage_mb=1.5, elapsed_time_ms=50),
        Verdict(passed=False, test_case_index=2, failure_cause=FailureCause.RUNTIME_ERROR, failure_detail="segmentation fault")
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
        Verdict(passed=False, test_case_index=2, failure_cause=FailureCause.WRONG_ANSWER)
    ]
    result4 = create_judgment_from_verdicts(verdicts4, **common_args)
    print(result4)
    print(result4.as_dict())
