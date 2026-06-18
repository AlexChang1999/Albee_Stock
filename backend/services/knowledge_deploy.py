"""
知識庫策略 → Paper Bot 部署（共用函式）
========================================
把一筆「已策展 / 已驗證」的 StrategyKnowledge 複製成 Paper Bot。手動端點
（POST /knowledge/{kid}/deploy）與自動部署排程（auto_deploy_knowledge）共用同一支，
確保「人按」與「排程建」行為一致、只有一處維護。

★ 安全紅線：一律建 **paper** bot（promotion_status="paper"），完全不碰真錢雙閘
  （ALPACA_BASE_URL 實盤 + ALLOW_LIVE_TRADING）。上真錢仍須走既有 promotion 流程。

knowledge 列**不綁標的**（驗證是跨籃子做的），部署時由呼叫端指定 symbols（一檔或多檔，
各建一個 Bot）。成功後戳 knowledge.deployed_at 當冪等戳記（排程才不會重複建）。
"""

from datetime import datetime

from backend.models import Bot
from backend.services import explorations


def normalize_symbols(symbols) -> list[str]:
    """把 symbols（str 或 list）正規化成去空白/去重/大寫的清單（保序）。"""
    raw = [symbols] if isinstance(symbols, str) else list(symbols)
    out: list[str] = []
    for s in raw:
        s = str(s).strip().upper()
        if s and s not in out:
            out.append(s)
    return out


def deploy_curated_to_bots(
    db,
    k,
    symbols,
    *,
    trade_amount: float = 1000.0,
    take_profit_pct: float | None = None,
    stop_loss_pct: float | None = None,
    trailing_stop_pct: float | None = None,
    check_interval_sec: int = 60,
    activate: bool = False,
) -> list[Bot]:
    """
    把一筆知識列複製成 N 個 Paper Bot（每個 symbol 一個）。**不 commit**（交給呼叫端）。

    :param k: StrategyKnowledge ORM 物件（會被戳 deployed_at）
    :param symbols: 要部署的標的（str 或 list；自動去空白/去重/大寫）
    :param activate: True = 建好即啟用（自動排程掛網跑 paper）；False = 人再手動 start
    :return: 建出的 Bot 清單（已 db.add，未 commit；呼叫端 commit 後才有 id）
    :raises ValueError: symbols 正規化後為空
    """
    syms = normalize_symbols(symbols)
    if not syms:
        raise ValueError("symbols 不可為空（至少指定一檔標的）")

    created: list[Bot] = []
    for sym in syms:
        bot = Bot(
            name=f"{k.name} @ {sym}",
            strategy=k.strategy_key,
            symbol=sym,
            params=k.params or {},
            trade_amount=trade_amount,
            take_profit_pct=take_profit_pct,
            stop_loss_pct=stop_loss_pct,
            trailing_stop_pct=trailing_stop_pct,
            check_interval_sec=check_interval_sec,
            is_active=activate,           # 自動部署 True 掛網跑；手動 False 人再 start
            promotion_status="paper",      # ★一律 Paper，不碰真錢雙閘
        )
        db.add(bot)
        created.append(bot)

    # 冪等戳記：成功部署後戳時間，排程才不會重複對同一筆知識建 Bot
    k.deployed_at = datetime.now()

    # 部署軌跡留檔（可追溯）
    how = "自動排程" if activate else "人工"
    reason = (f"由知識庫（status={k.status}）{how}部署成 {len(created)} 個 Paper Bot："
              f"{', '.join(syms)}。")
    explorations.write_knowledge_note(k.id, k.strategy_key, "deploy", reason)

    return created
