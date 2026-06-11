# Macro 層真資料驗證 Runbook（Backlog Item A / Phase 11 step-05 收尾）

> **✅ 已於 2026-06-11 執行完畢，結論：砍除。** 籃子定為 `SPY QQQ AAPL MSFT NVDA`；
> 真 FRED 資料（41,604 筆觀測）下 macro 列 **worth=False、folds=207、Δ=-101.68** →
> 走步驟 4 的「誠實砍」分支（移除 `MacroOverlayStrategy` 等，FRED 資料層保留）。
> 本檔留作歷史紀錄與未來同類驗證的範本。

> 對應 [`remaining-work-backlog.md` §A](../remaining-work-backlog.md) 與
> [Phase 11 step-05 藍圖](../history/phase-11-macro-data/step-05-macro-layer-validation.md)。
> 本檔是「拿到 FRED key 後照做即可」的機械式步驟單。**開工前先讀**
> [`ai-implementation-guardrails.md`](../ai-implementation-guardrails.md)。

## 為什麼還沒做完（唯一阻塞）

Phase 11 的程式全部就位（FRED client → `POST /macro/refresh` → `validate_layers()` macro 池 →
keep/cut 決策），**唯一缺的是一把免費 FRED API key**。沒有 key 時：

- `macro_features` 各欄全 NaN → `MacroOverlayStrategy` 退化成 baseline → 驗證印 `worth=False`。
- **這個 `worth=False` 不算數**：它只是「沒資料所以沒差別」，不是「有資料但證明無加分」。
  backlog §A 明訂：要砍 macro 層，必須是**灌入真 FRED 資料後**仍 `worth=False` 才誠實砍。

所以決策（留／砍）必須等真資料才能下。本 runbook 把那一步變成照表操課。

## 步驟 1 — 申請 FRED key 並填入 `.env`

1. 到 <https://fred.stlouisfed.org/docs/api/api_key.html> 免費註冊聖路易聯準會帳號、索取 API key
   （約 32 碼英數）。
2. 在專案根目錄 `.env` 加一行（`.env` 已被 git 忽略，**絕不 commit**）：
   ```
   FRED_API_KEY=你的_32碼_key
   ```
3. 序列清單沿用 `config.py` 預設 `MACRO_SERIES`（非農/失業率/聯邦基金/CPI/10年&2年殖利率/VIX），
   要改才動 `.env` 的 `MACRO_SERIES`。

## 步驟 2 — 灌入真 FRED 序列

啟後端，呼叫一次更新端點把序列抓進本機快取：

```powershell
venv\Scripts\uvicorn.exe backend.main:app --reload
```

另開一個 shell（或用 `http://127.0.0.1:8000/docs` 的 Swagger）打：

```
POST /macro/refresh
```

預期回 `{"refreshed": {"FEDFUNDS": N, ...}, "total": N>0}`。`total` 必須 **> 0**——若回 400
代表 key 沒讀到（檢查 `.env` 拼字、重啟後端讓 `config.py` 重讀）。

> 想抽查資料：`GET /macro/series?series_id=DGS10`（帶 `as_of=YYYY-MM-DD` 看 point-in-time 視角）。

## 步驟 3 — 跑層驗證

```powershell
venv\Scripts\python.exe scripts\validate_layers.py SPY <BASKET-TBD>
```

- **標的籃子（待定）**：使用者稍後決定。backlog 建議 `SPY` 再加幾檔大型權值股 / ETF
  （如 `QQQ AAPL MSFT NVDA`）以增加 walk-forward fold 數。**標的越多 → 池化樣本越多 → verdict
  越可信**，但跑越久。最終籃子敲定後回填這行並更新本 runbook。
- 資料源預設 yfinance（免金鑰）；macro 特徵走 DB session 取真 FRED 序列做 as-of 對齊。

## 步驟 4 — 判讀 verdict 並下決策

看輸出表的 **macro 列**：`worth | folds | base | cand | Δ(improvement)`。
`is_layer_worth_it` 的門檻：fold 數須 ≥ `settings.VALIDATION_MIN_FOLDS`（樣本太少不採信），
且 candidate 樣本外平均要贏過 baseline。

兩條路（嚴格照 backlog §A）：

- **`worth=True`（真資料下有 OOS 加分）→ 留**
  - 保留 `MacroOverlayStrategy`。
  - 把 `folds / Δ` 數據寫進 `CHANGELOG.md`，並在
    [`step-05-macro-layer-validation.md`](../history/phase-11-macro-data/step-05-macro-layer-validation.md)
    補一條「真資料驗證通過」註記。

- **`worth=False`（真資料、folds 足夠，仍無加分）→ 誠實砍**（沿用 Phase 7「沒加分就砍」紀律）：
  - `backend/services/layer_validation.py`：移除 `MacroOverlayStrategy` / `validate_macro_layer`，
    並從 `validate_symbol` 的回傳與 `validate_layers` 的 `pools` / `layer_names` 取下 `"macro"`。
  - `scripts/validate_layers.py`：印表迴圈 `("adaptive", "meta", "kelly", "macro")` 移除 `"macro"`。
  - `tests/test_macro_layer.py`：視保留範圍調整（純函式 / 門檻單測可留，整合測試隨被砍的 API 移除）。
  - `CHANGELOG.md`：記「真 FRED 資料下 macro 層仍無 OOS 加分 → 砍除」決策。

## DoD（完成定義）

- verdict 來自**真 FRED 資料**，且 macro 列 `folds ≥ VALIDATION_MIN_FOLDS`。
- 去留決策落 `CHANGELOG.md`：保留則附 `folds/Δ` 數據；砍除則程式 / 測試 / 文件同步清乾淨、無殘留。
