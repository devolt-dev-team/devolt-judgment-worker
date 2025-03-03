from common import get_env_var


class DockerConfig:
    """
    Description:
        Docker 설정 정보를 관리하는 클래스.
    """
    DOCKER_IMAGE = {
        "java17": get_env_var("SANDBOX_IMAGE_JAVA17"),
        "nodejs20": get_env_var("SANDBOX_IMAGE_NODEJS20"),
        "nodejs20esm": get_env_var("SANDBOX_IMAGE_NODEJS20"),
        "python3": get_env_var("SANDBOX_IMAGE_PYTHON3")
    }
