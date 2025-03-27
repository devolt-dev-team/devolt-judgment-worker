import datetime
from dataclasses import dataclass
import pytz
import uuid

from common import CodeLanguage, FailureCause
from schema import Schema, Verdict


@dataclass
class CodeChallengeJudgmentJob(Schema):
    """
    Description:
        코딩 챌린지 평가 작업(Job)의 상태를 Redis에 저장하고 불러올 때 활용하는 클래스

        @dataclass 어노테이션은 데이터를 저장하는 클래스를 만들 때 사용
        __init__, __eq__, __repr__ 등을 자동 관리해준다

    Attributes:
        job_id (str): 작업(Job)의 고유 ID (UUID)
        stop_flag (bool): 사용자에 의한 작업 중지 요청 여부

        code_language (CodeLanguage): 제출된 코드의 프로그래밍 언어
        code (str): 평가할 코드 문자열

        challenge_id (int): 코딩 챌린지 ID (문제 ID)
        total_test_cases (int): 테스트 케이스 총 개수
        verdicts (list[Verdict]): 각 테스트 케이스별 평가 기록

        submitted_at (str): 작업이 제출된 시각 (ISO 8601 형식, KST)
    """
    job_id: str
    stop_flag: bool

    code_language: CodeLanguage
    code: str

    challenge_id: int
    total_test_cases: int
    verdicts: list[Verdict]

    submitted_at: str

    def __post_init__(self):
        """객체 초기화 후 code_language를 문자열에서 CodeLanguage 객체로 변환"""
        if isinstance(self.code_language, str):
            self.failure_cause = CodeLanguage(self.code_language)

    @staticmethod
    def create(
        code_language: CodeLanguage,
        code: str,
        challenge_id: int,
        total_test_cases: int
    ) -> "CodeChallengeJudgmentJob": # 반환 타입 힌팅에 내부적으로 순환 참조를 막기 위해 문자열 힌팅 사용
        """
        Description:
            새로운 평가 작업을 생성하는 팩토리 메서드.
            - job_id를 UUID로 생성
            - 제출 시각(submitted_at)을 KST(한국 시간)으로 설정

        Args:
            code_language (CodeLanguage): 프로그래밍 언어
            code (str): 제출된 코드
            challenge_id (int): 평가할 챌린지(문제)의 ID
            total_test_cases (int): 총 테스트 케이스 개수

        Returns:
            CodeChallengeJudgmentJobEntity: 생성된 평가 작업 엔티티
        """
        seoul_tz = pytz.timezone('Asia/Seoul')
        now_in_seoul = datetime.datetime.now(seoul_tz)
        return CodeChallengeJudgmentJob(
            job_id=str(uuid.uuid4()),
            stop_flag=False,

            code_language=code_language,
            code=code,

            challenge_id=challenge_id,
            total_test_cases=total_test_cases,
            verdicts=[],

            submitted_at=now_in_seoul.strftime('%Y-%m-%dT%H:%M:%S')
        )

    @classmethod
    def create_from_dict(cls, judgment_job_dict: dict) -> "CodeChallengeJudgmentJob":
        """
        Description:
            부모 클래스 Schema의 create_from_dict를 호출한 뒤,
            code_language 필드를 CodeLanguage 객체로 변환하여 인스턴스를 생성합니다.

        Args:
            judgment_job_dict (dict): 입력 딕셔너리

        Returns:
            CodeChallengeJudgmentJob: 생성된 인스턴스
        """
        # 부모 클래스 Schema의 create_from_dict 호출
        instance = super().create_from_dict(judgment_job_dict)

        # code_language 변환 (문자열 -> CodeLanguage 객체)
        if isinstance(instance.code_language, str):
            instance.code_language = CodeLanguage(instance.code_language)

        return instance


# dict -> schema 변환 테스트: dict 필드 검증 및 인스턴스 반환
if __name__=='__main__':
    input_dict = {
        "passed": False,
        "testCaseIndex": 1,
        "failureCause": FailureCause.WRONG_ANSWER
    }

    verdict = Verdict.create_from_dict(input_dict)

    input_dict = {
        "jobId": "123-456",
        "stopFlag": False,

        "codeLanguage": CodeLanguage.JAVA17,
        "code": "hi",

        "challengeId": 1,
        "totalTestCases": 10,
        "verdicts": [
            verdict
        ],

        "submittedAt": "1234",
    }

    job = CodeChallengeJudgmentJob.create_from_dict(input_dict)
    print(job)
    print(job.as_dict())