from dataclasses import dataclass, fields
from enum import Enum
from typing import Any

from common import camel_to_snake, snake_to_camel, CodeLanguage


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

    def as_dict(self) -> dict[str, Any]:
        """
        객체를 사전(dict)로 변환합니다.
        키를 snake_case에서 camelCase로 변환하고,
        Enum 타입의 값은 .value를 사용하여 직렬화하며,
        중첩된 Schema 객체에 대해서는 재귀적 as_dict 변환을 수행합니다.
        """
        # 각 필드 순회하며 직접 처리
        result = {}

        for f in fields(self):
            value = getattr(self, f.name)
            # 값 처리
            processed_value = self._process_value(value)
            # 키 변환 및 결과 저장
            result[snake_to_camel(f.name)] = processed_value

        return result

    def _process_value(self, value):
        """타입에 따라 값을 변환하는 헬퍼 메서드"""
        if isinstance(value, Enum):
            return value.value
        elif isinstance(value, Schema):
            return value.as_dict()
        elif isinstance(value, dict):
            return {snake_to_camel(k) if isinstance(k, str) else k:
                        self._process_value(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [self._process_value(item) for item in value]
        return value