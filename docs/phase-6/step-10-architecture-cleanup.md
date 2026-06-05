# 步驟 10 — 架構與文件整理（無行為變更）

> 清技術債、消除漂移風險。回到 [Phase 6 索引](README.md)。

## 目標

把 5 個 Phase 堆疊出的文件 / 設定 / 跨層同步的混亂收乾淨，**不改任何執行行為**，
讓專案結構與文件對齊現況，降低未來再生 vibe slop 的機率。

## 待整理項

### 1. 統一 Phase 編號（目前三套互相打架）

- `CLAUDE.md`：Phase 1–5。
- `docs/redesign/`：另一套 Phase 1–4（圖表 / AI 推薦 / 主題 / 自動化）。
- `backend/config.py` 註解：把即時報價標成「Phase 6」、外送閘標成別的。

**改動**：在 `CLAUDE.md` 立**一張權威 Phase 對照表**，把 `docs/redesign/` 明確標為「Phase 2~4 的改版子軌」，
修正 `config.py` 註解裡的錯誤 Phase 標號（即時報價不是 Phase 6；本份「可信度地基」才是 Phase 6）。

### 2. 策略清單單一來源（消除三處手動同步）

現況：新增策略要同時改 `backend/strategies/__init__.py`（註冊）、`frontend/src/constants.js`（前端清單）等多處，靠人記得同步。

**改動**：
- 新增 `GET /strategies`（建議 `backend/routers/strategies.py`），回 `STRATEGY_REGISTRY` 的鍵 + 顯示名。
- 前端 `constants.js` 改由此端點載入（或至少加一個測試斷言前後端清單一致），消除漂移。

### 3. config 分組整理

把 `backend/config.py` 的 `Settings` 依領域分區、加區段註解，並把 Phase 6 新增的設定歸位：

```
Alpaca / DB / LLM / Screener / Automation / Backtest成本(P6) / OOS(P6) / Portfolio風控(P6) / Explorations
```

### 4. 文件同步

- `CLAUDE.md`：更新專案結構（新增 `decision_log` model、`capital.py`、`lookback.py`、`strategies` router 等）、
  「已知坑」補上「回測 = 實盤」鐵則與成本 / OOS 說明。
- `README.md`：進度表加 Phase 6、API 清單補 `GET /strategies`、`GET /bots/{id}/decisions`。
- `docs/phase-6/`：本資料夾即收錄整份計畫（已完成）。

## 重用既有

- `docs/redesign/` 的「索引 + 分階段」文件結構（本資料夾沿用）。
- `STRATEGY_REGISTRY`（已存在，只是還沒對外曝露成 API）。

## 測試

- `GET /strategies` 端點往返；測試斷言「後端註冊鍵集合 == 前端清單 value 集合」。
- 純文件 / 註解改動不需新測試，但須確保既有 `pytest` / 前端測試仍全綠。

## 驗收

- 任何人打開 `CLAUDE.md` 能在一張表看懂 Phase 1–6 的全貌，不再被三套編號搞混。
- 新增策略時，前端清單自動跟上（或測試會擋下不同步）。
- `pytest tests/` 與前端 `npm run test` 全綠。
