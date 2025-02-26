from dataclasses import dataclass
from typing import Optional

from schema import Schema


@dataclass
class SubmissionResult(Schema):
    user_id: int
    job_id: str
    challenge_id: int

    code_language: str
    code: str
    code_byte_size: int

    overall_pass: bool
    max_memory_used_mb : Optional[float]
    max_elapsed_time_ms: Optional[int]

    compile_error: Optional[str]
    runtime_error: Optional[str]

    submitted_at: str


# dict -> schema 변환 테스트: dict 필드 검증 및 인스턴스 반환
if __name__=='__main__':
    input_dict = {
        "userId": 1,
        "jobId": "1234",
        "challengeId": 1,

        "codeLanguage": "c",
        "code": "#include<stdio.h> void main() {}",
        "codeByteSize": 400,

        "overallPass": True,
        "maxMemoryUsedMb": 55.12,
        "maxElapsedTimeMs": 140,

        "compileError": None,
        "runtimeError": None,

        "submittedAt": "2025-12-23T00:00:30"
    }

    result = SubmissionResult.create_from_dict(input_dict)
    print(result)