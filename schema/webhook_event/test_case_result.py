from dataclasses import dataclass

from schema import Schema, Verdict


@dataclass
class TestCaseResult(Schema):
    job_id: str
    verdict: Verdict


# dict -> schema 변환 테스트: dict 필드 검증 및 인스턴스 반환
if __name__=='__main__':
    input_dict = {
        "passed": True,
        "testCaseIndex": 1,
        "memoryUsedMb": 15.2,
        "elapsedTimeMs": 120,
        "runtime_error": None,
        "compile_error": None
    }

    verdict = Verdict.create_from_dict(input_dict)

    test_case_result = TestCaseResult.create_from_dict({
        "jobId": "132-456",
        "verdict": verdict
    })

    print(test_case_result.as_dict())