"""
因子數值表 API（Phase 10 step-03）
====================================
唯讀端點：查詢 / 匯出常駐掃描落表的市場狀態因子快照（蒐集員主管的報表）。

定位：純讀 factor_snapshots 表，**因子是觀測佐證、不是交易訊號**——這裡不下單、
不建 Bot、不重算因子（因子的真實來源是 services/regime_features）。
"""

import csv
import io
from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import FactorSnapshot

router = APIRouter(tags=["Factors"])

# CSV / 序列化的欄位順序（固定，匯出與表格一致）
_COLUMNS = [
    "symbol",
    "as_of",
    "volume_ratio",
    "return_5d",
    "return_20d",
    "volatility_20d",
    "trend_strength",
    "atr_pct",
    "range_position",
    "regime",
]


def _serialize(f: FactorSnapshot) -> dict:
    return {
        "id": f.id,
        "symbol": f.symbol,
        "as_of": f.as_of.isoformat() if f.as_of else None,
        "volume_ratio": f.volume_ratio,
        "return_5d": f.return_5d,
        "return_20d": f.return_20d,
        "volatility_20d": f.volatility_20d,
        "trend_strength": f.trend_strength,
        "atr_pct": f.atr_pct,
        "range_position": f.range_position,
        "regime": f.regime,
    }


def _query(db: Session, symbol: Optional[str], limit: int):
    """共用查詢：可選 symbol 篩選、依 as_of 由新到舊、limit 夾在 1~1000。"""
    q = db.query(FactorSnapshot)
    if symbol:
        q = q.filter(FactorSnapshot.symbol == symbol.upper())
    return q.order_by(FactorSnapshot.as_of.desc()).limit(max(1, min(limit, 1000))).all()


@router.get("/factors")
def list_factors(
    symbol: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """
    列出因子快照，依觀測時點 as_of 由新到舊。

    :param symbol: 可選；只看某檔（不分大小寫）。不帶就回各檔混合的最近快照。
    :param limit: 最多回幾筆（夾在 1~1000）。
    """
    return [_serialize(f) for f in _query(db, symbol, limit)]


@router.get("/factors/export.csv")
def export_factors_csv(
    symbol: Optional[str] = None,
    limit: int = 1000,
    db: Session = Depends(get_db),
):
    """把因子快照匯出成 CSV（含表頭，欄位順序固定）。給人下載 / 丟進試算表分析。"""
    rows = _query(db, symbol, limit)

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(_COLUMNS)
    for f in rows:
        data = _serialize(f)
        writer.writerow([data[c] for c in _COLUMNS])
    buf.seek(0)

    filename = f"factors_{symbol.upper()}.csv" if symbol else "factors.csv"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
