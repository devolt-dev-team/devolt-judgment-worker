from common import get_env_var


class DockerConfig:
    """
    Description:
        Docker 설정 정보를 관리하는 클래스.
    """
    DOCKER_IMAGE = {
        "java": get_env_var("SANDBOX_IMAGE_JAVA17"),
    }
