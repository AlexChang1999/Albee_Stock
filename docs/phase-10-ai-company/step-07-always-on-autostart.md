# Phase 10 step-07 — 開機常駐化（Windows 自啟）

> 開工前必讀 [`../ai-implementation-guardrails.md`](../ai-implementation-guardrails.md)。
> 依賴：step-02（常駐掃描）。純 ops，**零交易邏輯改動**。

## 目標 / 概念

補「**電腦開機就一直跑**」：開機 → 後端自動起 → APScheduler 讓 Bot + 掃描 job 持續跑。
解決「記憶體排程、關 app 就停」的落差。

## 問題 / 改動

- 新增 ops 文件 + 一個註冊 **Windows 工作排程器**的 `.bat`（登入時觸發既有 `start_backend.bat`）。
- 文件說明：登入後自動啟動、失敗重試、看 log、怎麼停。

## 重用既有

- 既有 `start_backend.bat`；`main.py` 的 `lifespan` 已有 `_resume_active_bots` + `schedule_auto_deploy`
  （開機起來就會自動接回啟用中的 Bot 與盤前 cron）。

## 測試 / 驗收（DoD）

- 文件可照做：開機後 `GET /` / `/account` 有回應、啟用中的 Bot 有在排程、機會清單 job 有在跑。
- **無程式碼變更 → 不需跑 pytest**；屬 ops 驗證（手動照 checklist）。

## 風險 / 不要做

- **不**做成 Windows 系統服務 / NSSM 等重維運方案（增加複雜度；工作排程器夠用）。
- **不**在開機腳本裡塞交易邏輯——只負責「把後端拉起來」。
- 提醒：**常駐 ≠ 開實盤**。常駐跑的仍是 Paper，真錢仍受雙閘 + step-06 核准。
