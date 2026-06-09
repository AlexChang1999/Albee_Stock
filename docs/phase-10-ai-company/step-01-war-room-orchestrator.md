# Phase 10 step-01 — 戰情室編排 + 公司戰情頁（看得到的公司）

> 開工前必讀 [`../ai-implementation-guardrails.md`](../ai-implementation-guardrails.md)。本檔只補步驟專屬內容。
> 依賴：Phase 9（sidebar + 路由外殼）。

## 目標 / 概念

把現有各服務的狀態（帳戶 / 持倉 / Bot / 海選 / 自動部署 / 熔斷 / 機會清單）聚合成「**一頁看到整間公司**」，
讓「六角色 = 部門」這個比喻變成使用者看得到的東西。**純呈現層**，服務「系統可被信任、可追溯」這條原目標——
不新增任何 alpha、不改交易邏輯。

## 問題 / 改動

- 後端新增**唯讀**聚合端點 `backend/routers/company.py`（`GET /company/overview`）：把既有讀取點
  （帳戶、Bot 清單與啟用數、最近決策、自動化規則與名額、熔斷狀態、機會清單若 step-02 已做）組一包回傳。
  **不自己算交易 / EV**，只轉述既有服務結果。
- 前端新增 `frontend/src/pages/CompanyPage.jsx`（沿用 Phase 9 sidebar 路由，新增「公司戰情」項）：
  用「部門卡」呈現每個角色目前狀態 + 連到對應既有頁（策略主管→/backtest-runs、回測主管→/evolution…）。

## 重用既有

- 後端：`routers/bots.py`、`services/automation_config.get_config`、`services/circuit_breaker.check_breaker`、
  `models/decision_log`、`alpaca_client.get_account`——全部既有讀取，端點只聚合。
- 前端：`api.js` 加一支 `getCompanyOverview`；卡片配色吃 `theme.js` / `NEON`，**不寫死 hex**；
  沿用 `Stat.jsx` / `AccountCard` 既有元件風格。

## 測試 / 驗收（DoD）

- `GET /company/overview` 回傳結構穩定；離線（無 Alpaca 金鑰）時帳戶區塊 best-effort 給 None 不崩。
- 後端 `tests/test_company.py`（monkeypatch 各服務，驗聚合鍵齊全 + 離線降級）；
  前端 `CompanyPage.test.jsx`（部門卡渲染 + 連結）。
- `pytest tests/ -q` 與 `npm run test` 全綠。

## 風險 / 不要做

- **不**在這頁新增任何交易 / 部署動作（純看板）；動作仍走各既有頁。
- **不**在前端重算 EV / 勝率——只顯示後端數字。
- **不**寫死顏色（深藍主題隱形陷阱，見 CLAUDE.md）。
