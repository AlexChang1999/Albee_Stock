# 步驟 4 — 樣本外驗證：optimizer 以 OOS EV 排名 ★本 Phase 核心

> 修 **P1**（樣本內過擬合）。回到 [Phase 6 索引](README.md)。

## 目標

把「文件一直警告、optimizer 卻一直在犯」的過擬合，從口號變成**程式層的硬約束**：
挑冠軍、設部署門檻，一律看**樣本外（out-of-sample, OOS）**的表現，而非樣本內。

## 問題（現況）

`optimizer.run_auto_backtest` 把 ~40 組參數**在整段歷史上**跑、挑 in-sample EV 最高的當冠軍，
`screener` → `automation.plan_deployments` 直接部署這個冠軍。
這等於「在考卷上先偷看答案再宣稱滿分」——選出來的是最會擬合過去雜訊的參數，未來大機率失效。
這是整個自動交易系統最危險的科學缺陷，比成本問題更致命。

## 改動

1. 新增純函式 **`split_train_test(df, test_ratio=0.3)`**（時間序列切分，**測試段必須在時間軸後段、不可洗牌**）。
2. **`backend/services/optimizer.py`** 的 `run_auto_backtest`：
   - 對每組參數，分別在 train 段與 test 段各跑一次 `_run_on_df`，回傳 `in_sample` 與 `out_of_sample` 兩套 metrics。
   - **冠軍判定改用 `out_of_sample.expected_value`**（OOS EV）為主排序鍵，`out_of_sample.total_return_pct` 為次。
   - 對外新增欄位 `oos_expected_value` / `oos_win_rate_pct` 等（in-sample 仍保留供對照，看「掉多少」就知道過擬合多嚴重）。
3. **`backend/config.py`** 新增 `OOS_TEST_RATIO`（預設 `0.3`）。
4. **`backend/services/screener.py`** 取 best 時改看 OOS EV；
   **`backend/services/automation.py`** 的 `plan_deployments` 門檻**一律比對 OOS EV**。
   → 門檻語意從「in-sample EV」變「OOS EV」，須在 CHANGELOG 與 `.env.example` 明確註明（同一個 `AUTO_DEPLOY_EV_THRESHOLD` 數字現在更難達到，這是對的）。

## 重用既有

- `_run_on_df`（在切好的子 df 上各跑一次即可，不需新回測邏輯）。
- 既有 metrics 結構（OOS 套用同一份計算）。

## 測試

- 構造「train 段漂亮、test 段崩盤」的合成序列，驗證該組合**不會**被選為冠軍。
- 驗證排名鍵讀的是 `out_of_sample.expected_value` 而非 in-sample。
- 驗證 `split_train_test` 切分點正確、測試段在後、無洩漏。

## 驗收

- `POST /auto-backtest` 回傳同時含 in-sample 與 OOS 指標；冠軍是 OOS EV 最高者。
- 人工挑一個「in-sample EV 高但 OOS EV 低」的組合，確認它在排行榜落後。
- 模式 B 的部署門檻現在卡的是 OOS EV，過擬合的策略過不了關。
