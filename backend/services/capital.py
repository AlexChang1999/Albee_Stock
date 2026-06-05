"""
組合層資金 / 購買力守門（Phase 6 step-05）
===========================================
讓系統在「建 Bot」「下買單」前，先確認帳戶真的付得起，且永遠保留一筆現金緩衝。
防止模式 B 一次梭哈、並發下單互踩購買力。

核心是一個純函式 plan_capital：給一批「計畫部署」的推薦 + 帳戶可用現金 + 每個 Bot 配資 +
保留比例，逐筆核可、扣到不夠就把其餘歸入 rejected（附原因）。純函式好寫單元測試。
"""


def plan_capital(
    planned: list[dict],
    available_cash: float,
    cash_per_bot: float,
    reserve_ratio: float,
) -> tuple[list[dict], list[dict]]:
    """
    依「可動用現金」決定一批計畫部署裡，哪些建得起、哪些資金不足。

    規則：
    - 可動用額度 = available_cash ×(1 − reserve_ratio)（永遠保留 reserve_ratio 比例的現金）。
    - 依序核可 planned，逐筆扣 cash_per_bot；扣到剩餘額度不夠再配一個，
      其餘全部歸入 rejected（附 reason）。
    - cash_per_bot <= 0（不佔用資金）→ 全數核可（邊界情境）。
    - reserve_ratio 夾在 [0, 1]，防呆。

    :param planned: 已通過 EV/勝率/情緒等門檻、準備部署的推薦清單（順序即優先序）。
    :param available_cash: 帳戶可用現金（通常取 account.cash）。
    :param cash_per_bot: 每個 Bot 預計配置的資金。
    :param reserve_ratio: 永遠保留的現金比例（例 0.2 = 留 20%）。
    :return: (approved, rejected)。approved 為原推薦物件；rejected 為含 reason 的精簡 dict。
    """
    reserve_ratio = max(0.0, min(1.0, reserve_ratio))
    usable = max(0.0, float(available_cash)) * (1 - reserve_ratio)

    approved: list[dict] = []
    rejected: list[dict] = []

    # 配資為 0 或負：不佔用資金，全部核可
    if cash_per_bot <= 0:
        return list(planned), []

    spent = 0.0
    for rec in planned:
        # 1e-9 容忍浮點誤差（剛好夠時不要因尾數被誤判為不夠）
        if spent + cash_per_bot <= usable + 1e-9:
            approved.append(rec)
            spent += cash_per_bot
        else:
            rejected.append({
                "symbol": rec.get("symbol"),
                "strategy_key": rec.get("strategy_key"),
                "reason": "資金不足：可用購買力（已扣現金緩衝）不夠再配一個 Bot",
            })
    return approved, rejected
