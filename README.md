# 🚀 Devolt 코드 채점 Worker

**Devolt 채점 시스템의 MSA 기반 Worker 애플리케이션입니다.**  
Redis/Celery 메시지 브로커로부터 작업을 수신하며, Docker 컨테이너 샌드박스 환경에서 코드를 안전하게 실행하고 결과를 평가합니다. 평가 결과는 Spring Boot로 전달됩니다.


<br /><br />




## 🧱 채점 과정
### 채점 작업 수신
```
Redis -> Celery Worker -> Docker Container
```
- Celery Worker는 Redis 메시지 브로커로부터 작업을 수신하여 언어별 Docker 컨테이너에서 안전하게 실행합니다.
<br />

### 채점 결과 전달
```
Docker Container -> Celery Worker -> Spring Boot Backend
```
- 채점 결과는 WebHook 콜백을 통해 Spring Boot 백엔드로 직접 전송됩니다.
- 각 테스트 케이스 결과는 개별적으로 실시간 전송됩니다.

<br /><br />




## ✨ 주요 기능

- Celery 기반 비동기 작업 처리
- Docker 컨테이너 기반 샌드박스 환경 구현
- 다중 프로그래밍 언어 지원 (Java17, C11, C++17, Python3, NodeJS20)
- 실시간 채점 결과 전송
- 테스트 케이스별 상세 결과 제공 (컴파일 에러, 런타임 에러, 시간 초과, 메모리 초과 등)
- 컨테이너 보안정책 적용 (리소스 제한, 네트워크 격리, 시스템 콜 차단 등)
