from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    MYSQL_HOST: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = ""
    MYSQL_DATABASE: str = "stock_market_analyzer"
    DATABASE_URL: Optional[str] = None
    DART_API_KEY: str = ""
    KRX_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    REPORT_TIME: str = "18:30"
    MARKET: str = "KR"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    def get_database_url(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return (
            f"mysql+pymysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}?charset=utf8mb4"
        )


settings = Settings()

DISCLAIMER = (
    "본 분석은 가격, 거래량, 수급, 뉴스, 실적, 추세 데이터를 기반으로 생성된 참고용 시장 분석입니다.\n"
    "투자 판단은 사용자 본인 책임입니다."
)
