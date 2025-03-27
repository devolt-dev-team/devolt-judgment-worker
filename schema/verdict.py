from dataclasses import dataclass
from typing import Optional

from schema import Schema
from common import FailureCause


@dataclass
class Verdict(Schema):
    passed: bool
    test_case_index: Optional[int] = None
    memory_usage_mb: Optional[float] = None
    elapsed_time_ms: Optional[int] = None
    failure_cause: Optional[FailureCause] = None
    failure_detail: Optional[str] = None

    def __post_init__(self):
        """객체 초기화 후 failure_cause를 문자열에서 FailureCause 객체로 변환"""
        if isinstance(self.failure_cause, str):
            self.failure_cause = FailureCause(self.failure_cause)

    @classmethod
    def create_from_dict(cls, verdict_dict: dict) -> "Verdict":
        """
        Description:
            부모 클래스 Schema의 create_from_dict를 호출한 뒤,
            failure_cause 필드를 FailureCause 객체로 변환하여 인스턴스를 생성합니다.

        Args:
            verdict_dict (dict): 입력 딕셔너리

        Returns:
            Verdict: 생성된 인스턴스
        """
        # 부모 클래스 Schema의 create_from_dict 호출
        instance = super().create_from_dict(verdict_dict)

        # failure_cause 변환 (문자열 -> FailureCause 객체)
        if isinstance(instance.failure_cause, str):
            instance.failure_cause = FailureCause(instance.failure_cause)

        return instance


# dict -> schema 변환 테스트: dict 필드 검증 및 인스턴스 반환
if __name__=='__main__':
    input_dict = {
        "passed": True,
        "testCaseIndex": 1,
        "memoryUsageMb": 15.2,
        "elapsedTimeMs": 54,
        "failureCause": FailureCause.WRONG_ANSWER
    }

    verdict = Verdict.create_from_dict(input_dict)
    print(verdict)
    print(verdict.as_dict())


    verdict = Verdict(False, 1, None, None, FailureCause.WRONG_ANSWER.value)
    print(verdict)
    print(verdict.as_dict())