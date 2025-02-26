from common import get_env_var


class RedisConfig:
    """
    Description:
        Redis 설정 정보를 관리하는 클래스.
    """
    HOST = get_env_var("REDIS_HOST")
    PORT = get_env_var("REDIS_PORT", int)
    PASSWORD = get_env_var("REDIS_PASSWORD")
    DB = get_env_var("REDIS_DB", int)
    REDIS_URI = f'redis://:{PASSWORD}@{HOST}:{PORT}/{DB}'
