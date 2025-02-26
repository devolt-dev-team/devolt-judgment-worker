import os


def get_env_var(key: str, cast_func=lambda x: x):
    value = os.getenv(key)
    if value is None:
        raise ValueError(f"Environment variable '{key}' is not set.")
    try:
        return cast_func(value)
    except Exception as e:
        raise ValueError(f"Error converting environment variable '{key}': {e}") from e