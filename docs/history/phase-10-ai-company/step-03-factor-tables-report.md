# Phase 10 step-03 — 因子數值表 + 報表（蒐集員主管）

> 開工前必讀 [`../ai-implementation-guardrails.md`](../../ai-implementation-guardrails.md)。
> 依賴：Phase 7（regime_features）、step-01。

## 目標 / 概念

回應使用者「把影響的數據**列成數值、表**」：把市場狀態因子（量比 / 報酬 / 波動 / 趨勢強度…）落成
**可查、可匯出**的數值表 + 一頁報表。服務「決策可追溯」——因子是觀測佐證，不是新訊號。

## 問題 / 改動

- 新增 model `backend/models/factor_snapshot.py`（每檔每日：7 個因子 + 當下 regime 標籤 + `as_of`），
  走 Alembic 遷移。由 step-02 的週期 job 順手寫入（同一次抓資料、不另外多抓）。
- 新增唯讀 `GET /factors`（依 symbol / 日期查）+ `GET /factors/export.csv`（CSV 匯出）。
- 前端新增 `pages/FactorsPage.jsx`：表格呈現各檔最新因子 + 歷史趨勢；沿用既有表格 / 卡片風格。

## 重用既有

- `services/regime_features.compute_features`（**已算 7 因子，勿重造**）、`services/regime.classify_regime`。
- step-02 的週期 job（因子在那次掃描順手落表，呼應「資料只抓一次」）。
- 前端既有表格元件 + `theme` / `NEON` 配色。

## 測試 / 驗收（DoD）

- `tests/test_factor_snapshot.py`（寫入 / 查詢 / CSV 欄位正確 + **無 look-ahead**：只用截至 `as_of` 的資料）。
- `FactorsPage.test.jsx`（表格渲染 + 匯出鈕）。
- Alembic `upgrade head`；`pytest tests/ -q`、`npm run test` 全綠。

## 風險 / 不要做

- **不**讓因子表自動變成交易訊號（它是「蒐集員主管的報表」，給人和回測看的）。
- **不**重算因子或自創第二套公式——一律走 `regime_features`。
- **不**無上限存歷史（給保留天數設定，避免 DB 膨脹）。
