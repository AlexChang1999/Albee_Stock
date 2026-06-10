# 步驟 5 — ★macro 層 OOS 加分驗證

> **Phase 11 能不能信的關鍵。** 沒有它，前 4 步只是「用總經數據更精緻地騙自己」。回到 [Phase 11 索引](README.md)。

## 目標

用樣本外（OOS）walk-forward，證明「加上 macro 特徵」真的贏過「純價量 baseline」。
**沒加分就砍**——macro 層加不了分時，如實標記並移除，不硬留（沿用 Phase 7 防過擬合框架）。

## 為什麼這步最重要

step-03 / step-04 每加一欄環境特徵，就多一個可調旋鈕。
**旋鈕越多，越容易在歷史上找到一組「看起來完美」、對未來卻沒用的設定。**
這是量化交易最大死因。所以 macro 層必須先過 OOS 驗證才准上線，否則記錄「試過、無效、砍掉」也是成果。

## 改動構想

- `backend/services/layer_validation.py`：新增 macro 層的
  **baseline(純價量) vs candidate(+macro)** 比較——同策略、同區間、同 walk-forward 切分，
  唯一差別是 candidate 多吃 step-03 的 macro / 買賣壓特徵（透過 step-04 的 `features` 管線）。
- `scripts/validate_layers.py`：把 macro 層納入印表，輸出每層 `worth | folds | improvement` 判決。
- 沿用 `validation.walk_forward_splits` 切時序、`is_layer_worth_it(baseline_oos, candidate_oos)`
  判定（內建最小提升門檻 + 樣本數檢查）。

## 重用現有

- `services/validation.py` 的 `walk_forward_splits` / `is_layer_worth_it`（Phase 7 step-07 已建）。
- `services/layer_validation.py` 既有的 baseline-vs-candidate harness（macro 只是新增一個 candidate 層）。
- step-04 的 `features` 參數當 candidate 的差異來源；step-02 的 `bar_cache` 供多年價格。

## 過擬合風險（這步本身的紀律）

- **這套是用來「殺掉沒用的層」，不是用來「美化績效」**——希望它把 macro 判死，那才是它在工作。
- **挑冠軍 / 設門檻一律看 OOS**：不可在整段歷史挑樣本內最佳（過擬合）。
- 別偷看測試段調參數；macro 特徵的任何門檻只能在訓練段內決定。

## 驗收（DoD）

- 構造一個「in-sample 漂亮、OOS 崩」的假 macro 層 → `is_layer_worth_it` 正確判它**不值得上線**。
- 對 SPY 跑「純價量 baseline vs +macro candidate」多年 walk-forward：
  ```powershell
  venv\Scripts\python.exe scripts\validate_layers.py
  ```
  印出 macro 層 `worth | folds | improvement` 判決；沒加分如實標 **不值得**（並在 CHANGELOG 記錄砍除）。
- 純 / 半整合測試（合成資料驗判定邏輯，不依賴外部 API）。
