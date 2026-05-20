import threading

# pykrx는 내부적으로 전역 HTTP 세션을 사용해 thread-safe하지 않음.
# 여러 서비스가 병렬로 pykrx를 호출할 때 이 락으로 직렬화한다.
_lock = threading.Lock()
