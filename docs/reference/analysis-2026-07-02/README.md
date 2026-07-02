# 回測驗證日總報告（2026-07-02）

> 今日目標：不跑 Paper/實盤，完成整套系統的回測驗證、掃頻研究、股票池體檢與資金流分析。
> 所有結論都有數據支持；子報告與原始 CSV 在本資料夾，重跑腳本在 `scripts/`。

## 0. 系統驗證結果（含當場修掉的問題）

| 檢查項 | 結果 |
|---|---|
| pytest 全套 | 首輪 603 過 / **5 失敗** → 修復後全綠（見下方修改清單） |
| 後端啟動 | 本機以 **follower**（唯讀 API）模式運行——VM 為排程 leader，本機不下單 |
| VM（Oracle）服務 | `albee-backend` active（main@00d07f1），休市自動跳過，正常 |
| API smoke | `/status` `/strategies` `/positions` `/backtest-runs` 正常；`/bots` 原本 **57 秒** → 修 N+1 後正常 |
| 資料抓取 | 38 檔 × 3 年日 K + 30 天分鐘 K 抓取成功（6 檔 DNS 瞬斷已補跑） |
| 下單驗證 | 全程零下單（本機 follower + 休市 + 未觸發任何交易路徑） |

**當場發現並修復的錯誤：**

1. `script_breakout` 新策略漏接指標疊圖映射 + 向量化豁免清單（2 個測試炸）。
2. `layer_validation` 的兩個包裝策略缺 `produce_signals`（回測引擎統一入口改版後漏改，3 個測試炸）。
3. `/bots` API 對 190 個 Bot 逐檔打 Alpaca + 逐檔查 TradeLog（2×190 次網路往返 = 57 秒）→ 改批次（固定 2 次往返）。
4. `catchup.py` 開機補跑在 cp950 主控台印 emoji 會把整個補跑 job 炸掉（實測踩到）→ 編碼失敗退回 ASCII。
5. 回測引擎不模擬停損/停利（「回測=實盤」缺口）→ 新增 opt-in 模擬（預設關、舊行為 bit-for-bit 不變，含 6 個新測試）。

**⚠️ 發現但未修（需要使用者決定）：排程選主鎖的「靜默失鎖」問題。**
VM 的 advisory lock 連線曾被 Neon 掐斷（鎖已釋放），但 VM 只在開機時檢查一次、之後繼續自以為
leader 跑排程；期間本機另一個卡住的實例搶到了鎖 → **理論上會出現雙 leader 重複下單**。今天已把
本機殭屍實例清掉，但根治需要：(a) 重啟 VM 服務讓它重新拿鎖（今日被權限擋下，請自行
`sudo systemctl restart albee-backend`）；(b) 加「leader 定期驗鎖 + 失鎖自動重搶/自貶」機制（建議下一步）。

## 1. 回測報告（38 檔 × 9 策略 × 參數網格，3 年，OOS 排名）

詳表：[backtest-report.md](backtest-report.md)｜原始資料：backtest-champions.csv / backtest-leaderboard.csv

方法：含成本（5bps 滑價）+ 隔日開盤成交 + 樣本外（後 30%）EV 排名挑冠軍 + 蒙地卡羅 500 路徑壓力測試。

組合層彙總（38 檔冠軍）：

| 指標 | 中位數 | 平均 | 範圍 |
|---|---|---|---|
| 整段報酬（3 年） | 62.8% | 98.1% | −12.2% ~ 576.3% |
| CAGR | 17.8% | 22.8% | −4.3% ~ 90.1% |
| Sharpe | 1.04 | 0.93 | −0.02 ~ 1.88 |
| 最大回撤 | 23.8% | 27.8% | 0.1% ~ 74.1% |
| 勝率 | 75% | 75.4% | 33% ~ 100% |
| Profit Factor（有虧損的 25 檔） | 4.72 | — | — |

**誠實揭露（很重要）：**

- 只有 **17/38** 檔冠軍贏過 Buy & Hold——過去 3 年是大多頭，波段策略天生吃虧，這不是 bug，但要知道。
- 蒙地卡羅顯示回撤 >20% 的機率中位數 **61.6%**——現行組合不是低風險組合。
- **OOS 樣本嚴重不足**：38 檔中 32 檔的 OOS 段 round trips 只有 1~2 筆，其「100% 勝率、高 EV」
  是小樣本噪音，**不可當已證實的 edge**（詳見股票池報告）。根治法＝改用 walk-forward 多折
  驗證（`validation.walk_forward_splits` 已存在，只是 optimizer 還沒接）。

**風控對照組**（停損 7%/停利 15%/追蹤 10%；艦隊現況＝三者全未設）：

- 報酬變好：12/38 檔；**回撤變小：29/38 檔**（平均 MDD 27.8% → 20.9%）
- 代價：平均報酬 98% → 42%（停利 15% 觸發 155 次，砍掉了長波段的大肉）
- 結論：**這組參數不建議照抄**。停利太緊傷報酬；值得單獨測「只設停損 / 只設追蹤止損」變體
  （回測引擎現在支援，一行參數就能跑）。

## 2. 最佳掃盤時間：**維持 300 秒**（現況正確，不用改）

詳表：[scan-frequency.md](scan-frequency.md)

| 事實 | 數據 |
|---|---|
| 策略吃日 K，訊號一天只變一次 | 掃頻**完全不影響進場時機**（30s 和 600s 看到同一根日 K） |
| 掃頻只影響風控出場延遲 | 但艦隊 190 個 Bot **全部沒設停損/停利** → 現況連出場都不受影響 |
| 若未來啟用停損（分鐘 K 實測 798 symbol-日） | 觸發本來就少（30 天僅 24 次）；300s 中位額外滑價 ≈ **−2.8bps（可忽略）**；600s 才開始痛（+32bps） |
| API 用量（190 bots） | 60s → 190 req/min ≈ **打滿** Alpaca 200/min 上限；300s → 38 req/min（81% 餘裕） |

結論：300s 是「日 K 策略 + 190 bots + 免費 API」下的甜蜜點。**把錢花在刀口上的不是調掃頻，
而是（a）啟用風控出場（b）縮小股票池**。若池縮到核心 6~12 檔（30~60 bots），可安全降到 120s，
但在日 K 策略下這只改善風控出場延遲，期望收益差異 ≈ 0。

## 3. 股票池：38 檔確實太多，但「剔除依據」還不夠格——先分層降級，別急著砍

詳表：[stock-pool.md](stock-pool.md)｜原始資料：stock-pool.csv

- **核心池（OOS 樣本 ≥3 筆且 EV>0，已證實）**：AMD、AVGO、INTC、ORCL、BAC、MS（6 檔）
- **觀察池（OOS EV>0 但樣本 1~2 筆，未證實）**：其餘 32 檔
- **建議剔除（OOS EV≤0）**：0 檔

你的直覺對了一半：**38 檔對「驗證品質」來說太多**——每檔分到的 OOS 交易數太少，排行榜上的
高 EV 大多是統計噪音；且 190 bots 把 API 限流吃到只剩 300s 一檔選擇。但反過來，沒有任何一檔
是「樣本外負期望」的明確垃圾，所以**現在砍池的依據不足**。建議路徑：

1. 先跑 walk-forward 多折驗證（把 OOS 樣本從 1~2 筆放大到 10+ 筆），用可信的 EV 重新分層；
2. 同質性高的半導體 10 檔（NVDA/AMD/AVGO/TSM/INTC/QCOM/MU/AMAT/LRCX/ASML）相關性極高，
   佔了池的 1/4——即使全部 EV>0，也建議只留 RS 最強的 3~4 檔（分散度比檔數重要）；
3. 指數 ETF 5 檔（SPY/QQQ/DIA/IWM/VTI）互相重疊嚴重，留 SPY+QQQ 即可；
4. 依 1~3 收斂到 **15~20 檔**後，bots 從 190 → ~80，API 餘裕翻倍，檢討與監控的注意力也集中。

## 4. 資金流分析

詳表：[fund-flow.md](fund-flow.md)｜原始資料：fund-flow.csv

- 方法：11 檔 SPDR 產業 ETF vs SPY 相對強度（1/5/20 日）+ 量比 + tick-rule 買賣壓 proxy
  （誠實標註：免費日 K 推導的 proxy，非真實逐筆資金流）。
- 今日快照：強勢產業與領漲股見子報告；「隔日發動候選」今日 1 檔（條件全滿足才列，不硬湊）。
- **納入策略的路線圖**（報表因子 → 入庫累積 60 天 → 既有 OOS 閘驗證有無加分 → 有加分才上線，
  無加分誠實砍，同 Phase 11 macro 層先例）。目前**不**直接接下單。

## 5. 自動化能力檢查表

| 能力 | 狀態 | 對應 |
|---|---|---|
| 自動抓歷史資料 | ✅ | market_data + bar_cache（本機 parquet 快取） |
| 自動篩股 | ✅ | screener 三層漏斗 + opportunity_scan 常駐 |
| 自動回測 | ✅ | backtest_engine + vectorized_engine（快 10×） |
| 自動比較不同策略 | ✅ | optimizer.run_auto_backtest（9 策略 × 網格，OOS 排名） |
| 自動產生報表 | ✅（本次補齊） | scripts/full_backtest_report.py 等 4 支 CLI |
| 自動找最佳參數 | ✅ | optimizer 參數網格 + OOS 挑冠軍 |
| 週期性全池體檢 | ⬜ 建議 | 把 4 支腳本掛進每週排程（見下一步） |

## 6. 已修改程式清單

| 檔案 | 改了什麼 |
|---|---|
| `backend/services/backtest_engine.py` | opt-in 停損/停利/追蹤止損模擬 + exit_reason + 觸發統計（預設關，舊行為不變） |
| `backend/routers/bots.py` | `/bots` N+1 修成批次（57s → 秒級） |
| `backend/services/layer_validation.py` | 兩個包裝策略改繼承 BaseStrategy（修 produce_signals 缺失） |
| `backend/services/indicator_overlays.py` | 補 script_breakout 疊圖映射 |
| `backend/services/catchup.py` | cp950 印 emoji 炸掉補跑 job → 編碼失敗退 ASCII |
| `backend/services/notifier.py` | notify 的主控台 print 在 cp950 下炸掉會連 Discord 推播一起死 → log 失敗不擋推播 |
| `tests/test_vectorized_engine.py` | 向量化豁免改 ScriptStrategy 子類原則判斷 |
| `tests/test_backtest.py` | 新增 6 個風控出場模擬測試 |
| `scripts/full_backtest_report.py` ✚ | 全池回測報告 CLI（新增） |
| `scripts/scan_frequency_study.py` ✚ | 掃頻研究 CLI（新增） |
| `scripts/stock_pool_report.py` ✚ | 股票池體檢 CLI（新增） |
| `scripts/fund_flow_report.py` ✚ | 資金流分析 CLI（新增） |

## 7. Git Diff

完整 diff 見本次 PR（分支 `worktree-backtest-validation-day` → `develop`）。

## 8. 下一步建議（依優先序）

1. **重啟 VM 服務重拿 leader 鎖**（一行指令），並實作「leader 定期驗鎖」防雙 leader 重複下單
   ——這是唯一可能造成真金損失的已知風險。
2. **optimizer 接上 walk-forward 多折驗證**（工具已存在），把 OOS 樣本放大到可信水準，
   再據以砍池（38 → 15~20 檔）與重挑冠軍。
3. **用新引擎測「只停損」與「只追蹤止損」變體**（本次數據顯示停利 15% 傷報酬、停損/追蹤
   降回撤有效）——挑 OOS 上證實加分的組合再上艦隊。
4. 資金流因子入庫累積 60 天 → OOS 驗證 → 決定去留。
5. 4 支報告腳本掛週排程（heartbeat 同路），每週一自動產出全池體檢。
6. 過擬合警訊常態化：把「IS EV vs OOS EV 落差」與「OOS 樣本數」加進 optimizer 排行榜的
   顯示欄位，讓每次挑冠軍都看得到樣本量。
