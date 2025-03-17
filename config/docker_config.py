from common import get_env_var
from common.enums import CodeLanguage


class DockerConfig:
    """
    Description:
        Docker 설정 정보를 관리하는 클래스.
    """
    SANDBOX_IMAGE_NAME = {
        CodeLanguage.JAVA17.value: get_env_var("SANDBOX_IMAGE_JAVA17"),
        CodeLanguage.NODEJS20.value: get_env_var("SANDBOX_IMAGE_NODEJS20"),
        CodeLanguage.NODEJS20ESM.value: get_env_var("SANDBOX_IMAGE_NODEJS20ESM"),
        CodeLanguage.PYTHON3.value: get_env_var("SANDBOX_IMAGE_PYTHON3"),
        CodeLanguage.C11.value: get_env_var("SANDBOX_IMAGE_CLANG15"),
        CodeLanguage.CPP17.value: get_env_var("SANDBOX_IMAGE_CLANG15")
    }

    SANDBOX_SCRIPT_PATH = {
        CodeLanguage.JAVA17.value: get_env_var("SANDBOX_SCRIPT_PATH_JAVA17"),
        CodeLanguage.NODEJS20.value: get_env_var("SANDBOX_SCRIPT_PATH_NODEJS20"),
        CodeLanguage.NODEJS20ESM.value: get_env_var("SANDBOX_SCRIPT_PATH_NODEJS20ESM"),
        CodeLanguage.PYTHON3.value: get_env_var("SANDBOX_SCRIPT_PATH_PYTHON3"),
        CodeLanguage.C11.value: get_env_var("SANDBOX_SCRIPT_PATH_C11"),
        CodeLanguage.CPP17.value: get_env_var("SANDBOX_SCRIPT_PATH_CPP17")
    }

    SECCOMP_PROFILE_PATH = get_env_var("SECCOMP_PROFILE_PATH")
