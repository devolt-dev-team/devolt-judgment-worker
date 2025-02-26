from dataclasses import dataclass

from schema import Schema


@dataclass
class JobCancellation(Schema):
    job_id: str

# dict -> schema 변환 테스트: dict 필드 검증 및 인스턴스 반환
if __name__=='__main__':
    input_dict = {
        "jobId": "132-45"
    }

    error = JobCancellation.create_from_dict(input_dict)
    print(error)