import redis

from .exception import RedisConnectionError


class RedisConnection:
    """
    Description:
        Redis 설정 Client 객체를 제공하는 클래스.
        DI(의존성 주입) 방식으로, 외부에서 Redis 연결에 필요한 설정(host, port, password, db)을 주입받아 인스턴스를 생성.
    """

    def __init__(self, host, port, password, db):
        self._host = host
        self._port = port
        self._password = password
        self._db = db
        self._client = None
        self._connect()

    def _connect(self):
        """
        Description:
            job.StrictRedis 객체 생성 및 client 필드 초기화 & ping 테스트
        """
        try:
            client = redis.StrictRedis(
                host=self._host,
                port=self._port,
                password=self._password,
                db=self._db
            )
            # 연결 테스트
            client.ping()
            self._client = client
            self._print_redis_success()

        except redis.exceptions.AuthenticationError as e:
            self._client = None  # 실패 시 클라이언트 초기화
            raise RedisConnectionError(f"Redis authentication failed: {e}")
        except redis.exceptions.RedisError as e:
            self._client = None
            raise RedisConnectionError(f"Failed to connect to Redis: {e}")
        except Exception as e:
            self._client = None
            raise RedisConnectionError(f"Unexpected error during Redis initialization: {e}")

    @staticmethod
    def _print_redis_success():
        """
        Description:
            Redis 연결 성공 메시지를 터미널에 출력
            클래스 내부 속성에 의존하지 않으므로 staticmethod로 정의
        """
        msg = " Successfully connected to Redis! "
        border = "─" * len(msg)

        print("\n\033[92m" + "┌" + border + "┐" + "\033[0m")
        print("\033[92m" + "│" + msg + "│" + "\033[0m")
        print("\033[92m" + "└" + border + "┘" + "\033[0m\n")

    @property
    def client(self) -> redis.StrictRedis:
        """
        Description:
            외부에서 'redis_conn.client' 로 접근 시,
            내부적으로 connect()가 보장된 후 실제 클라이언트를 반환.
        """
        if self._client is None:
            self._connect()
        return self._client
