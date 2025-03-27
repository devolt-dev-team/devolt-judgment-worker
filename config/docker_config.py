import os

from common import get_env_var
from common.enums import CodeLanguage


class DockerConfig:
    """
    Description:
        Docker 설정 정보를 관리하는 클래스.
    """
    _SANDBOX_IMAGE_NAME = {
        CodeLanguage.JAVA17: get_env_var("SANDBOX_IMAGE_JAVA17"),
        CodeLanguage.NODEJS20: get_env_var("SANDBOX_IMAGE_NODEJS20"),
        CodeLanguage.NODEJS20ESM: get_env_var("SANDBOX_IMAGE_NODEJS20ESM"),
        CodeLanguage.PYTHON3: get_env_var("SANDBOX_IMAGE_PYTHON3"),
        CodeLanguage.C11: get_env_var("SANDBOX_IMAGE_CLANG15"),
        CodeLanguage.CPP17: get_env_var("SANDBOX_IMAGE_CLANG15")
    }

    _SANDBOX_SCRIPT_PATH = {
        CodeLanguage.JAVA17: get_env_var("SANDBOX_SCRIPT_PATH_JAVA17"),
        CodeLanguage.NODEJS20: get_env_var("SANDBOX_SCRIPT_PATH_NODEJS20"),
        CodeLanguage.NODEJS20ESM: get_env_var("SANDBOX_SCRIPT_PATH_NODEJS20ESM"),
        CodeLanguage.PYTHON3: get_env_var("SANDBOX_SCRIPT_PATH_PYTHON3"),
        CodeLanguage.C11: get_env_var("SANDBOX_SCRIPT_PATH_C11"),
        CodeLanguage.CPP17: get_env_var("SANDBOX_SCRIPT_PATH_CPP17")
    }

    _SECCOMP_PROFILE_PATH = os.path.join(os.path.dirname(__file__), "json", "seccomp-profile.json")

    _CODE_FILE_NAME = {
        CodeLanguage.JAVA17: 'Main.java',
        CodeLanguage.NODEJS20: 'main.js',  # CommonJS
        CodeLanguage.NODEJS20ESM: 'main.mjs',  # ESM
        CodeLanguage.PYTHON3: 'main.py',
        CodeLanguage.C11: 'main.c',
        CodeLanguage.CPP17: 'main.cpp'
    }

    @staticmethod
    def get_sandbox_image_name_and_script_path(code_language: CodeLanguage) -> tuple[str, str]:
        return DockerConfig._SANDBOX_IMAGE_NAME[code_language], DockerConfig._SANDBOX_SCRIPT_PATH[code_language]

    @staticmethod
    def get_seccomp_profile_path() -> str:
        return DockerConfig._SECCOMP_PROFILE_PATH

    @staticmethod
    def get_source_code_file_name(code_language: CodeLanguage) -> str:
        return DockerConfig._CODE_FILE_NAME[code_language]


