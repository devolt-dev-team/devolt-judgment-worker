from dataclasses import asdict, dataclass, fields

from common import camel_to_snake, snake_to_camel


@dataclass
class Schema:
    @classmethod
    def validate_keys(cls, schema_dict: dict):
        """
        입력된 딕셔너리의 각 camelCase(또는 snake_case) 키를 snake_case로 변환한 후,
        해당 클래스의 필드 이름과 모두 일치하는지 확인합니다.

        (cls 인자를 통해 현재 호출한 클래스를 직접 참조하기 위해 static 대신 @classmethod 사용)
        """
        valid_fields = {f.name for f in fields(cls)}
        for key in schema_dict.keys():
            converted_key = camel_to_snake(key)
            if converted_key not in valid_fields:
                raise ValueError(
                    f"Invalid key in input dict: '{key}' (converted to '{converted_key}') "
                    f"is not a valid field for {cls.__name__}"
                )

    @classmethod
    def create_from_dict(cls, schema_dict: dict) -> "Schema":
        """
        부모 클래스에서 전체 구현을 제공하여, 입력 딕셔너리의
        camelCase 또는 snake_case 키를 모두 snake_case로 변환한 뒤,
        해당 클래스의 생성자에 전달하여 인스턴스를 생성합니다.

        (cls 인자를 통해 현재 호출한 클래스를 직접 참조하기 위해 static 대신 @classmethod 사용)
        """
        cls.validate_keys(schema_dict)
        processed_dict = {camel_to_snake(key): value for key, value in schema_dict.items()}

        # 동적 필드를 넘기는 부분을 정확히 추론하지 못해서 발생하는 IDE의 경고는
        # 이미 입력 값을 validate_keys를 통해 검증 하였기 때문에 무시
        return cls(**processed_dict)

    def as_dict(self) -> dict[str, any]:
        """
        dataclasses.asdict를 이용해 객체를 사전(dict)로 변환합니다.
        추가로, 키를 snake_case에서 camelCase로 변환합니다.
        """
        raw = asdict(self)
        return {snake_to_camel(k): v for k, v in raw.items()}
