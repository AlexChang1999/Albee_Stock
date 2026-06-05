# 步驟 4 — 分數凱利部位

> 區塊 3。回答你的「可投多少量（%）」。回到 [Phase 7 索引](README.md)。

## 目標

把「勝率 X%、賠率 Y → 該下注本金的多少 %」用數學算出來，取代目前每個 Bot 寫死的固定 `trade_amount`。

## 概念名稱

**凱利公式（Kelly Criterion）** + **分數凱利（Fractional Kelly）**。

公式（單筆下注版）：
```
f* = W − (1 − W) / R
  W = 勝率（用 OOS 勝率）
  R = 賠率 = 平均賺 / 平均賠（用 OOS avg_win / avg_loss）
f* = 建議下注本金比例
```
實務**只用 ¼~½ 個 f\***（分數凱利），因為：全凱利波動極大、且我們的 W/R 是「估計值」，估錯時全凱利會爆倉。

## 為什麼可行

- 我們**已經算出 W（win_rate）與 R 的原料（avg_win / avg_loss）**，Phase 6 後這些還是「含成本的 OOS」版本——正好是凱利該吃的誠實輸入。

## 改動構想

- 新增純函式 `backend/services/sizing.py`：`kelly_fraction(win_rate, avg_win, avg_loss, cap, fraction) -> float`：
  - 算 `f*`，乘上 `fraction`（分數凱利係數），再用 `cap`（單檔上限，如 20%）夾住。
  - `f* <= 0`（沒有正期望）→ 回 0（不下注）。
- `config.py` 新增 `KELLY_FRACTION`（預設 0.25）、`KELLY_MAX_FRACTION`（單檔上限，預設 0.2）。
- Bot 建立 / 自動部署時，`trade_amount` 改為「可用資金 × kelly_fraction(...)」（與 Phase 6 [步驟 5 資金守門](../phase-6/step-05-capital-guard.md) 串接，總曝險仍受購買力與保留比例約束）。

## 重用現有

- 回測 metrics 的 `win_rate_pct` / `avg_win` / `avg_loss`（已存在）。
- Phase 6 [步驟 5](../phase-6/step-05-capital-guard.md) 的 `plan_capital`（凱利算出的部位仍要過總資金守門）。

## 過擬合 / 風險

- **凱利對輸入估計極敏感**：W 高估一點，建議部位就暴衝。**所以一定要用 OOS 的 W/R + 分數凱利 + 硬上限**三重保守。
- 樣本太少（交易筆數不足）時 W/R 不可信 → 退回固定小額或不下注。
- 凱利假設「賠率分布穩定」，現實會變——分數凱利 + 上限就是為了容錯。

## 驗收

- `kelly_fraction` 純函式：手算驗證（如 W=0.6、R=2 → f\*=0.4，¼ 凱利 → 0.1）。
- 負期望（f\*≤0）回 0、不下注；上限正確夾住暴衝值。
- 部位最終仍受 Phase 6 資金守門約束（不會因凱利建議就超過購買力）。
