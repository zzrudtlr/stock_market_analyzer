from datetime import date
from typing import Optional

from fastapi import APIRouter, Query

from app.services.price_service import get_price_history
from app.services.stock_service import get_stock_by_code, get_stocks

router = APIRouter()


@router.get("/")
def list_stocks(
    market: Optional[str] = Query(None, description="KOSPI 또는 KOSDAQ"),
    limit: int = Query(100, le=5000),
):
    return get_stocks(market=market, limit=limit)


@router.get("/{stock_code}")
def get_stock(stock_code: str):
    stock = get_stock_by_code(stock_code)
    if not stock:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="종목을 찾을 수 없습니다.")
    return stock


@router.get("/{stock_code}/prices")
def get_stock_prices(stock_code: str, days: int = Query(60, ge=5, le=250)):
    df = get_price_history(stock_code, days=days)
    if df.empty:
        return []
    df["trade_date"] = df["trade_date"].astype(str)
    return df.to_dict(orient="records")
