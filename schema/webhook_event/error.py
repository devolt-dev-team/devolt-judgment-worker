from dataclasses import dataclass

from schema import Schema


@dataclass
class Error(Schema):
    job_id: str
    detail: str = "Internal server error"

# dict -> schema 변환 테스트: dict 필드 검증 및 인스턴스 반환
if __name__=='__main__':
    input_dict = {
        "job_id": "123-456",
        "detail": "알 수 없는 오류 입니다."
    }

    error = Error.create_from_dict(input_dict)
    print(error)