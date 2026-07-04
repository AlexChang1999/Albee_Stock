# Phase 16 最終報告（M12）

- 產出日期：2026-07-03；資料：核心 6 檔 × 730 天，walk-forward 聚合 OOS
- 漏斗 checkpoint：Round1 48 格 / Round2 120 格 / Round3 48 格 / Round4(M10) 48 格

## 1. 架構修改摘要（Phase 16）

| 里程碑 | 內容 | 關鍵產物 |
|---|---|---|
| M1 | 選主鎖修復（租約制 + 下單第三閘） | scheduler_lock / lease daemon |
| M2 | 多 timeframe 資料地基（1Min~1Day 全鏈） | services/timeframes.py、bar_cache 分框架存 |
| M3/M3.5 | walk-forward 聚合 OOS + 排名守門 + 前端欄位 | optimizer._wf_aggregate、overfit_gap |
| M4 | 可插拔出場政策（fixed_pct/atr/swing/vwap + R:R） | services/exit_policies.py，回測實盤共用 |
| M5 | 進場趨勢過濾器框架（6 filters） | services/trend_filters.py |
| M6 | 研究矩陣四輪漏斗（本報告數據來源） | scripts/warm_cache.py、scripts/research_matrix.py |
| M7 | RS 模組 + 股票池瘦身建議 38→20 | services/relative_strength.py、sectors.py |
| M8 | 日內單一掃描迴圈（批次抓全池） | bot_manager.run_intraday_scan + 預取快取 |
| M9 | 4 支報告腳本進 scheduler（週一自動） | bot_manager.schedule_weekly_reports |
| M10 | AI Decision Layer（規則式 entry gate + 動態出場） | services/decision_layer.py、AdaptiveExitPolicy |

## 2. 修改檔案清單（Phase 16 主要）

- 新增：`backend/services/timeframes.py`、`exit_policies.py`、`trend_filters.py`、`relative_strength.py`、`sectors.py`、`decision_layer.py`
- 新增：`scripts/warm_cache.py`、`scripts/research_matrix.py`、`scripts/final_report.py`
- 修改：`backend/services/optimizer.py`（walk-forward 聚合 + 守門）、`backtest_engine.py`（exit_policy 掛點）、`bot_manager.py`（M8 掃描迴圈 + M4 實盤出場）、`alpaca_client.py`（token bucket 限流 + 批次 API）、`config.py`（相關開關）
- 測試：`tests/test_exit_policies.py`、`test_trend_filters.py`、`test_decision_layer.py`、`test_intraday_scan.py`、`test_optimizer_walkforward.py`、`test_timeframes.py` 等

## 3. 回測流程（誠實性設計）

1. 資料：Alpaca IEX 免費源 → 本機 parquet 快取（`warm_cache.py` 預熱；稀疏率體檢 RTH 5~8%，品質足夠、免上付費數據）。
2. 模擬：訊號於**次根開盤成交**（不偷看未來）、含滑價 5bps；出場觸價 intrabar 保守（同根破兩邊先算 stop）。
3. 驗證：walk-forward 滾動切分（fold 窗按 bar 密度換算成等效交易日 180/60/60），**所有排名/守門只看跨折聚合 OOS**（交易 ≥20、過擬合差距 ≤0.5、EV>0）。
4. 漏斗：Round 1 timeframe 海選 → Round 2 stop×R:R → Round 3 filters → Round 4 AI decision layer，逐層 `is_layer_worth_it`，加不了分就砍。

## 4. Walk-forward 結果 + 5. OOS 統計 + 6. Timeframe 比較（Round 1）

- 池：核心 6 檔（stock-pool 體檢核心池）× 9 策略 × 8 timeframe × 730 天
- 表格值 = 守門通過檔的平均聚合 OOS EV（$/筆，$10k 本金）；「通過」= OOS 交易 ≥20 且 gap ≤0.5 且 EV>0

| timeframe | 冠軍策略 | 通過檔數 | 平均OOS EV | 平均OOS交易 | 年交易估 | 判讀 |
|---|---|---|---|---|---|---|
| 1Min | momentum | 4/6 | 247.5 | 27.8 | 19.4 | 可用 |
| 5Min | ma_crossover | 4/6 | 21.7 | 337.5 | 247.5 ⚠️PDT | 可用 |
| 15Min | ma_crossover | 5/6 | 53.5 | 163.6 | 120.0 | 甜蜜點 |
| 30Min | donchian | 6/6 | 54.1 | 93.7 | 70.1 | 甜蜜點 |
| 1Hour | bollinger | 6/6 | 210.5 | 31.0 | 23.1 | 甜蜜點 |
| 2Hour | rsi | 5/6 | 272.1 | 26.2 | 18.9 | 甜蜜點 |
| 4Hour | rsi | 5/6 | 213.9 | 25.4 | 18.4 | 甜蜜點 |
| 1Day | stochastic | 5/6 | 82.6 | 43.0 | 36.1 | 甜蜜點 |

**判讀**：甜蜜點在 30Min~4Hour（多檔普遍通過、EV 高、年交易 17~80 次無 PDT）；1Min 幾乎全滅（僅 momentum）、1Day 僅 stochastic 存活。完整榜單見 `research-matrix-round1.md`。

## 7. Stop strategy 比較（Round 2）

每 (timeframe, 策略) 比：baseline（純訊號出場）vs 各出場政策最佳者：

| timeframe | 策略 | baseline EV | 最佳出場組合 | 其 EV | 出場有加分？ |
|---|---|---|---|---|---|
| 1Min | momentum | 260.2（4檔） | fixed_sl0.05_rr1.5 | 100.1（4檔） | ❌ 沒贏 |
| 5Min | bollinger | 19.7（4檔） | fixed_sl0.05 | 12.5（4檔） | ❌ 沒贏 |
| 5Min | ma_crossover | 21.7（4檔） | fixed_sl0.05_rr4 | 25.8（3檔） | ❌ 沒贏 |
| 5Min | momentum | 179.8（3檔） | fixed_sl0.05_rr2.2 | 94.6（3檔） | ❌ 沒贏 |
| 15Min | bollinger | 38.2（5檔） | swing20_rrNone | 15.1（6檔） | ✅ 贏 |
| 15Min | ma_crossover | 53.6（5檔） | fixed_sl0.05_rr4 | 54.9（5檔） | ✅ 贏 |
| 15Min | rsi | 24.1（5檔） | fixed_sl0.05_rr2.5 | 18.3（4檔） | ❌ 沒贏 |
| 30Min | adx_trend | 51.8（6檔） | swing20_rrNone | 29.1（6檔） | ❌ 沒贏 |
| 30Min | bollinger | 100.5（6檔） | swing20_rr4 | 60.2（6檔） | ❌ 沒贏 |
| 30Min | donchian | 54.0（6檔） | fixed_sl0.05_rr4 | 53.1（6檔） | ❌ 沒贏 |
| 1Hour | bollinger | 212.1（6檔） | swing20_rrNone | 189.3（6檔） | ❌ 沒贏 |
| 1Hour | ma_crossover | 98.1（5檔） | swing20_rr2.2 | 37.8（6檔） | ✅ 贏 |
| 1Hour | rsi | 111.7（6檔） | swing20_rrNone | 74.3（6檔） | ❌ 沒贏 |
| 2Hour | bollinger | 258.5（5檔） | swing20_rr3 | 224.2（5檔） | ❌ 沒贏 |
| 2Hour | donchian | 191.5（5檔） | swing20_rr1.5 | 94.6（6檔） | ✅ 贏 |
| 2Hour | rsi | 272.1（5檔） | swing20_rrNone | 174.0（5檔） | ❌ 沒贏 |
| 4Hour | macd | 79.3（6檔） | swing20_rr4 | 94.7（6檔） | ✅ 贏 |
| 4Hour | rsi | 213.9（5檔） | swing20_rrNone | 150.2（5檔） | ❌ 沒贏 |
| 4Hour | williams_r | 184.1（5檔） | swing20_rrNone | 108.7（5檔） | ❌ 沒贏 |
| 1Day | stochastic | 82.6（5檔） | atr2.0_rr1.5 | 78.1（6檔） | ✅ 贏 |

**結論**：20 組比較中，出場政策贏過 baseline 的只有 6 組——**均值回歸型策略（rsi/bollinger）掛 stop 反而砍掉回彈利潤**，訊號出場已是強基準。出場政策的價值在「定義 R、供券商端 GTC 保護單」（實盤防斷線）而非拉 EV。

## 8. R:R 比較（Round 2，跨所有存活組合）

| rr | 樣本組數 | 平均 OOS EV |
|---|---|---|
| 無 target（只SL） | 36 | 74.4 |
| 1.5 | 53 | 61.7 |
| 2 | 53 | 64.7 |
| 2.2 | 53 | 65.4 |
| 2.5 | 54 | 66.5 |
| 3 | 54 | 68.5 |
| 4 | 52 | 70.4 |

**判讀**：rr 越大 EV 遞增（target 越遠越不截斷趨勢），rr=None/4 通常最好——與第 7 節同一結論：這批策略的出場截斷傷害 > 保護收益。

## 9. 股票池縮減依據 + 10. 半導體 RS 篩選（M7）

- 規則：OOS EV>0 才有資格；指數 ETF 保留；**同 sector 只留 RS 綜合分前 3**（RS = 1/5/20 日「報酬 − SPY」等權）；上限 20（核心池優先）。
- 結果：38 → 20 檔（建議 `.env` 字串已產出，**人核准後才改**）。
- 半導體 sector（NVDA/AMD/AVGO/TSM/INTC/QCOM/MU/AMAT/LRCX/ASML 10 檔）RS 篩選留：**AMAT（RS 11.2）、LRCX（3.98）、ASML（1.84）**——科技股同池競爭下 RS 前 3；核心池的 AMD/AVGO/INTC 因 RS 落後未進瘦身清單，但 OOS 樣本最足（本研究矩陣即用它們驗證）。
- 完整依據表：`docs/reference/analysis-2026-07-02/stock-pool.md`。

## 11. Scanner 效能分析（M8）

- 舊：38 bot × 各自 interval job 各抓 K 線 → 30s 掃描 = 76+ req/min，撞免費版 200 上限。
- 新：單一 30s job：每 timeframe 1 次 `get_bars_multi` + 1 次 `get_latest_prices` + 1 次 `list_positions` ≈ **6 req/min**（降 ~92%），逐 bot 派發走既有 run_bot_once（零分岔）。
- 進場訊號只用已收完 bar；快取過期自動退回單檔路徑；1Day bot 保留 per-bot job（300s）。
- 單輪耗時：程式內建量測（目標 <5s），**盤中實測待常駐機器開跑後回填**。

## 12. IS vs OOS 過擬合分析（Round 1 全格）
- 可算 gap 的組合 218 組（gap = (IS−OOS)/|IS|；IS≤0 無意義不計）。
- gap > 0.5（樣本外掉超過一半，守門沉底）：53 組（24%）。
- gap < 0（OOS 反而優於 IS，健康）：115 組（53%）。
- 防線：排名守門直接沉底高 gap 組合 + 挑冠軍只看跨折聚合 OOS（樣本 ≥20 筆）——「1~2 筆 100% 勝率」的假冠軍在 stock-pool 體檢已驗證過是噪音。

### 附：Filters（Round 3） worth 摘要

| 層 | 建議上線的 timeframe（worth ≥3 檔且改善總和 >0） |
|---|---|
| adx_min | 1Min, 5Min, 4Hour |
| bos | 5Min |
| ema_stack | 30Min, 2Hour |
| hh_hl | 5Min, 15Min, 30Min, 1Hour, 4Hour |
| regime | 30Min, 4Hour |
| vwap_side | 1Min, 5Min, 15Min, 30Min, 2Hour, 4Hour |

詳表：`research-matrix-round3.md`

### 附：AI Decision Layer（Round 4 / M10） worth 摘要

| 層 | 建議上線的 timeframe（worth ≥3 檔且改善總和 >0） |
|---|---|
| adaptive_exit | 1Day |
| decision_gate | 5Min |
| gate+adaptive | 1Day |

詳表：`research-matrix-round4-m10.md`

## 13. 最終建議上線組合

（filter / decision layer 欄 = 該 timeframe「worth ≥3 檔且改善總和 >0」的層；逐 timeframe 各自判定，加不了分就不掛）

| timeframe | 策略 | 出場 | filter | decision layer | PDT | 建議 |
|---|---|---|---|---|---|---|
| 1Min | momentum | baseline | vwap_side, adx_min | 不掛 | — | 觀察 |
| 5Min | ma_crossover | baseline | vwap_side, adx_min, hh_hl, bos | decision_gate | ⚠️ | 觀察 |
| 15Min | bollinger | swing20_rrNone | vwap_side, hh_hl | 不掛 | — | 觀察 |
| 30Min | bollinger | baseline | ema_stack, vwap_side, hh_hl, regime | 不掛 | — | ★ 主力 |
| 1Hour | bollinger | baseline | hh_hl | 不掛 | — | ★ 主力 |
| 2Hour | donchian | swing20_rr1.5 | ema_stack, vwap_side | 不掛 | — | ★ 主力 |
| 4Hour | macd | swing20_rr4 | vwap_side, adx_min, hh_hl, regime | 不掛 | — | ★ 主力 |
| 1Day | stochastic | atr2.0_rr1.5 | 不掛 | adaptive_exit, gate+adaptive | — | 觀察 |

**建議**：
1. **主力 timeframe：1Hour~2Hour**（bollinger/rsi 6 檔普遍通過、OOS EV 200+/筆、年交易 ~20 次無 PDT）；30Min/4Hour 次之。
2. **出場**：多數組合 baseline（訊號出場）EV 最高，但實盤仍建議掛 champion 出場政策（swing/atr）供券商端 GTC 保護——付少量 EV 買斷線保護，屬保險費。
3. **池**：先跑 M7 瘦身後 20 檔（等人核准 `.env`）；研究矩陣證據來自核心 6 檔，擴池後建議重跑 Round 1 驗證外推性。
4. **人在迴路**：以上僅建議，上線與改 `.env` 由人決定；真錢另過董事會核准（Phase 10）。

