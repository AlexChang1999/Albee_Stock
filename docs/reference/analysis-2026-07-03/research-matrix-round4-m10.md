# 研究矩陣 Round 4 —— M10 AI Decision Layer 驗證

- 日期：2026-07-03；study_tag：`m10-layer-2026-07-03`
- 輸入：Round 2 每 timeframe 冠軍（策略 × 出場組合）；每 filter 用 `validation.is_layer_worth_it` 逐 fold OOS 判去留
- 判準：fold 數 ≥3 且 OOS 平均 EV 提升 ≥0.0（worth=True 才值得上線）
- **加不了分就砍**（M5 框架建好 ≠ 該上線；macro 層的教訓）

## 1Min —— 冠軍：momentum + baseline（Round 2 平均 OOS EV 260.25，通過 4 檔）

| symbol | decision_gate | adaptive_exit | gate+adaptive |
|---|---|---|---|
| AMD | ✅ +0 | ❌ -13 | ❌ -13 |
| AVGO | ✅ +0 | ❌ -357 | ❌ -357 |
| BAC | ✅ +0 | ✅ +1 | ✅ +1 |
| INTC | ✅ +0 | ❌ -603 | ❌ -603 |
| MS | ✅ +0 | ❌ -97 | ❌ -97 |
| ORCL | ✅ +0 | ❌ -287 | ❌ -287 |
| **worth 檔數** | **6/6** | **1/6** | **1/6** |

## 5Min —— 冠軍：ma_crossover + baseline（Round 2 平均 OOS EV 21.71，通過 4 檔）

| symbol | decision_gate | adaptive_exit | gate+adaptive |
|---|---|---|---|
| AMD | ✅ +0 | ❌ -58 | ❌ -58 |
| AVGO | ✅ +0 | ❌ -11 | ❌ -11 |
| BAC | ✅ +0 | ❌ -2 | ❌ -2 |
| INTC | ✅ +0 | ❌ -42 | ❌ -42 |
| MS | ✅ +0 | ❌ -10 | ❌ -10 |
| ORCL | ✅ +0 | ❌ -22 | ❌ -22 |
| **worth 檔數** | **6/6** | **0/6** | **0/6** |

## 15Min —— 冠軍：bollinger + swing20_rrNone（Round 2 平均 OOS EV 15.11，通過 6 檔）

| symbol | decision_gate | adaptive_exit | gate+adaptive |
|---|---|---|---|
| AMD | ✅ +3 | ❌ -26 | ❌ -26 |
| AVGO | ❌ -15 | ❌ -28 | ❌ -27 |
| BAC | ✅ +0 | ❌ -18 | ❌ -18 |
| INTC | ❌ -6 | ❌ -52 | ❌ -51 |
| MS | ✅ +0 | ❌ -28 | ❌ -28 |
| ORCL | ❌ -6 | ❌ -33 | ❌ -33 |
| **worth 檔數** | **3/6** | **0/6** | **0/6** |

## 30Min —— 冠軍：bollinger + baseline（Round 2 平均 OOS EV 100.53，通過 6 檔）

| symbol | decision_gate | adaptive_exit | gate+adaptive |
|---|---|---|---|
| AMD | ❌ -22 | ❌ -94 | ❌ -92 |
| AVGO | ✅ +7 | ❌ -66 | ❌ -65 |
| BAC | ❌ -3 | ❌ -38 | ❌ -37 |
| INTC | ✅ +14 | ❌ -215 | ❌ -211 |
| MS | ❌ -16 | ❌ -160 | ❌ -163 |
| ORCL | ❌ -1 | ❌ -36 | ❌ -37 |
| **worth 檔數** | **2/6** | **0/6** | **0/6** |

## 1Hour —— 冠軍：bollinger + baseline（Round 2 平均 OOS EV 212.14，通過 6 檔）

| symbol | decision_gate | adaptive_exit | gate+adaptive |
|---|---|---|---|
| AMD | ❌ -39 | ❌ -333 | ❌ -328 |
| AVGO | ✅ +11 | ❌ -161 | ❌ -161 |
| BAC | ✅ +0 | ❌ -43 | ❌ -41 |
| INTC | ❌ -43 | ❌ -330 | ❌ -330 |
| MS | ✅ +0 | ❌ -247 | ❌ -235 |
| ORCL | ❌ -3 | ❌ -236 | ❌ -247 |
| **worth 檔數** | **3/6** | **0/6** | **0/6** |

## 2Hour —— 冠軍：donchian + swing20_rr1.5（Round 2 平均 OOS EV 94.59，通過 6 檔）

| symbol | decision_gate | adaptive_exit | gate+adaptive |
|---|---|---|---|
| AMD | ✅ +0 | ❌ -249 | ❌ -249 |
| AVGO | ✅ +0 | ❌ -44 | ❌ -44 |
| BAC | ✅ +0 | ❌ -86 | ❌ -86 |
| INTC | ✅ +0 | ❌ -179 | ❌ -179 |
| MS | ✅ +0 | ❌ -4 | ❌ -4 |
| ORCL | ✅ +0 | ✅ +35 | ✅ +35 |
| **worth 檔數** | **6/6** | **1/6** | **1/6** |

## 4Hour —— 冠軍：macd + swing20_rr4（Round 2 平均 OOS EV 94.72，通過 6 檔）

| symbol | decision_gate | adaptive_exit | gate+adaptive |
|---|---|---|---|
| AMD | ✅ +0 | ❌ -149 | ❌ -149 |
| AVGO | ✅ +0 | ❌ -78 | ❌ -78 |
| BAC | ✅ +0 | ❌ -35 | ❌ -35 |
| INTC | ✅ +0 | ❌ -98 | ❌ -98 |
| MS | ✅ +0 | ❌ -69 | ❌ -69 |
| ORCL | ✅ +0 | ❌ -43 | ❌ -43 |
| **worth 檔數** | **6/6** | **0/6** | **0/6** |

## 1Day —— 冠軍：stochastic + atr2.0_rr1.5（Round 2 平均 OOS EV 78.08，通過 6 檔）

| symbol | decision_gate | adaptive_exit | gate+adaptive |
|---|---|---|---|
| AMD | ❌ -10 | ✅ +5 | ✅ +8 |
| AVGO | ❌ -15 | ❌ -24 | ❌ -20 |
| BAC | ✅ +10 | ✅ +1 | ✅ +12 |
| INTC | ✅ +3 | ✅ +61 | ✅ +67 |
| MS | ✅ +1 | ❌ -14 | ❌ -13 |
| ORCL | ❌ -19 | ✅ +33 | ✅ +40 |
| **worth 檔數** | **3/6** | **4/6** | **4/6** |

## 判讀規則

- filter 在該 timeframe「worth 檔數 ≥ 3」才建議上線；其餘一律不掛（改 HOLD 的每一筆都是放棄的利潤，沒有 OOS 證據就不付這個代價）。

