import logging
import sys
from pathlib import Path


def setup_logger(name: str = "stock_analyzer", log_dir: str = "logs") -> logging.Logger:
    Path(log_dir).mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    def _attach_handlers(lg: logging.Logger) -> None:
        if lg.handlers:
            return
        lg.setLevel(logging.INFO)
        console = logging.StreamHandler(sys.stdout)
        console.setFormatter(formatter)
        lg.addHandler(console)
        fh = logging.FileHandler(f"{log_dir}/app.log", encoding="utf-8")
        fh.setFormatter(formatter)
        lg.addHandler(fh)

    # "app" 네임스페이스에 핸들러를 붙여 app.main, app.database 등 모든 앱 로거를 커버
    # propagate=False 로 uvicorn root handler 중복 출력 방지
    app_ns = logging.getLogger("app")
    _attach_handlers(app_ns)
    app_ns.propagate = False

    named = logging.getLogger(name)
    _attach_handlers(named)

    return named


logger = setup_logger()
