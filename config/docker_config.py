from common import get_env_var


class DockerConfig:
    """
    Description:
        Docker 설정 정보를 관리하는 클래스.
    """
    SANDBOX_IMAGE_NAME = {
        "java17": get_env_var("SANDBOX_IMAGE_JAVA17"),
        "nodejs20": get_env_var("SANDBOX_IMAGE_NODEJS20"),
        "nodejs20esm": get_env_var("SANDBOX_IMAGE_NODEJS20"),
        "python3": get_env_var("SANDBOX_IMAGE_PYTHON3"),
        'c11': get_env_var("SANDBOX_IMAGE_CLANG15"),
        'cpp17': get_env_var("SANDBOX_IMAGE_CLANG15")
    }

    SANDBOX_SCRIPT_PATH = {
        "java17": get_env_var("SANDBOX_SCRIPT_PATH_JAVA17"),
        "nodejs20": get_env_var("SANDBOX_SCRIPT_PATH_NODEJS20"),
        "nodejs20esm": get_env_var("SANDBOX_SCRIPT_PATH_NODEJS20"),
        "python3": get_env_var("SANDBOX_SCRIPT_PATH_PYTHON3"),
        'c11': get_env_var("SANDBOX_SCRIPT_PATH_C11"),
        'cpp17': get_env_var("SANDBOX_SCRIPT_PATH_CPP17")
    }

    SECCOMP_PROFILE_PATH = get_env_var("SECCOMP_PROFILE_PATH")
