# 步驟 7 — ★防過擬合驗證框架（橫跨全部的鐵律）

> **這是整個 Phase 7 能不能信的關鍵。** 沒有它，前面 6 步都是「用更複雜的方法更精緻地騙自己」。
> 回到 [Phase 7 索引](README.md)。

## 目標

提供一套**嚴謹的時序驗證機制**，讓「狀態分類器、自適應選策略、meta-labeling」這些加上去的層，
**都必須在真正的樣本外資料上證明自己有加分**，否則一律砍掉。

## 為什麼這步最重要

Phase 7 每加一層（特徵、狀態、選擇、meta、凱利）就多一批可調的旋鈕。
**旋鈕越多，越容易在歷史上找到一組「看起來完美」的設定，而它對未來毫無用處。**
這是量化交易最大的死因。Phase 6 [步驟 4](../phase-6/step-04-out-of-sample-validation.md) 的單純 train/test 切分是起點，
但對「含 ML 的多層系統」還不夠，需要更強的工具。

## 概念名稱與工具

| 工具 | 解決什麼 |
|------|----------|
| **Walk-Forward Analysis（滾動前進驗證）** | 模擬「真實上線」：在過去訓練、在緊接的未來測試，往前滾 |
| **Purged K-Fold + Embargo（清洗式交叉驗證）** | 金融時序專用（López de Prado）：移除訓練 / 測試交界會洩漏未來的重疊樣本 |
| **Deflated Sharpe / 多重測試校正** | 你試了 N 組設定，最好的那組「漂亮」可能純屬運氣——校正掉這個偏誤 |
| **樣本外才算數的鐵則** | 任何「加層」的績效，只認 OOS / walk-forward 的數字 |

## 改動構想

- 新增 `backend/services/validation.py`：
  - `walk_forward(df, train_window, test_window, step) -> list[fold_metrics]`。
  - `purged_kfold_splits(n, k, embargo)`（給學習式模型用）。
  - `is_layer_worth_it(baseline_oos, candidate_oos) -> bool`（「這層有沒有在 OOS 上贏過不加它」的判定，內建最小提升門檻 + 樣本數檢查）。
- **規範**：步驟 2/3/5 的學習式版本、步驟 3 的對照表，**全部**要先過 `is_layer_worth_it` 才准上線。
- `config.py`：walk-forward 視窗、k、embargo、最小提升門檻等參數。

## 重用現有

- Phase 6 [步驟 4](../phase-6/step-04-out-of-sample-validation.md) 的 `split_train_test`（walk-forward 是它的滾動推廣）。
- `_run_on_df`（在每個 fold 的子 df 上跑回測）。

## 過擬合 / 風險（這步本身的紀律）

- **這套框架是用來「殺掉沒用的層」，不是用來「美化績效」**——心態要對：希望它把你心愛的點子判死，那才是它在工作。
- 別偷看測試段調參數（那就破功了）；參數搜尋只能在訓練段內做。

## 驗收

- `walk_forward` 對一個策略回出多個 fold 的 OOS 績效，數字明顯比單純 in-sample 保守。
- 構造一個「in-sample 漂亮、OOS 崩」的假層，`is_layer_worth_it` 正確判它**不值得上線**。
- Phase 7 任一新層上線前，都有一份 walk-forward 報告證明它在 OOS 加分；加不了分的層被移除（CHANGELOG 記錄「試過、無效、砍掉」也是成果）。
