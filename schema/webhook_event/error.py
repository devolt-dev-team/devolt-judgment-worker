from dataclasses import dataclass

from schema import Schema


@dataclass
class Error(Schema):
    job_id: str
    error: str = "Internal server error"

# dict -> schema 변환 테스트: dict 필드 검증 및 인스턴스 반환
if __name__=='__main__':
    input_dict = {
        "job_id": "123-456"
    }

    error = Error.create_from_dict(input_dict)
    print(error)