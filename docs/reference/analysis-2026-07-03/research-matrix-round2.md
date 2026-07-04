# 研究矩陣 Round 2 —— stop × R:R（M6）

- 日期：2026-07-03；study_tag：`m6-round2-2026-07-03`
- 輸入：Round 1 存活組合（每 timeframe 前 3 且守門通過 ≥3 檔）
- 出場網格：atr/swing × rr∈{None,1.5,2,2.2,2.5,3,4}、fixed_pct 四型（只SL/只Trailing/SL+Trailing/SL+Target）、vwap（僅日內）
- 守門：OOS 交易 ≥20 且 OOS EV>0；排名鍵 =（通過檔數, 平均 OOS EV）
- **判讀基準**：每張表第一列 baseline（無出場政策 = 純訊號出場）。出場組合沒贏過 baseline 就不值得加。

## 1Min

### momentum

| 出場組合 | 型 | 通過檔數 | 平均OOS EV | 平均交易 | 勝率% | PF | 平均R | 通過檔 |
|---|---|---|---|---|---|---|---|---|
| **baseline** | 訊號出場 | 4/6 | 260.25 | 27.5 | 46.76 | 2.26 | None | AMD,AVGO,INTC,ORCL |
| fixed_sl0.05_rr1.5 | SL+Target | 4/6 | 100.11 | 48.5 | 45.91 | 1.46 | 0.21 | AMD,AVGO,INTC,ORCL |
| fixed_sl0.05_rr2.2 | SL+Target | 4/6 | 92.72 | 42.75 | 41.23 | 1.4 | 0.2 | AMD,AVGO,INTC,ORCL |
| fixed_sl0.05_rr3 | SL+Target | 4/6 | 88.19 | 39.75 | 37.44 | 1.37 | 0.2 | AMD,AVGO,INTC,ORCL |
| fixed_sl0.05_rr2 | SL+Target | 4/6 | 85.05 | 44.75 | 40.36 | 1.36 | 0.19 | AMD,AVGO,INTC,ORCL |
| swing20_rr2 | SL+Target | 4/6 | 81.65 | 45.0 | 38.31 | 1.4 | 0.08 | AMD,AVGO,INTC,ORCL |
| fixed_sl0.05_rr2.5 | SL+Target | 4/6 | 76.29 | 42.0 | 38.54 | 1.31 | 0.18 | AMD,AVGO,INTC,ORCL |
| fixed_tr0.05 | 只Trailing | 4/6 | 64.94 | 45.5 | 42.25 | 1.37 | None | AMD,AVGO,INTC,ORCL |
| fixed_sl0.05 | 只SL | 3/6 | 155.6 | 33.67 | 34.78 | 1.63 | 0.35 | AVGO,INTC,ORCL |

## 5Min

### bollinger

| 出場組合 | 型 | 通過檔數 | 平均OOS EV | 平均交易 | 勝率% | PF | 平均R | 通過檔 |
|---|---|---|---|---|---|---|---|---|
| **baseline** | 訊號出場 | 4/6 | 19.69 | 300.0 | 61.95 | 1.32 | None | AMD,AVGO,INTC,MS |
| fixed_sl0.05 | 只SL | 4/6 | 12.47 | 317.75 | 61.35 | 1.21 | 0.03 | AMD,AVGO,INTC,MS |
| fixed_sl0.05_rr4 | SL+Target | 4/6 | 12.47 | 317.75 | 61.35 | 1.21 | 0.03 | AMD,AVGO,INTC,MS |
| fixed_sl0.05_rr3 | SL+Target | 4/6 | 12.1 | 317.75 | 61.35 | 1.2 | 0.03 | AMD,AVGO,INTC,MS |
| fixed_sl0.05_rr2.5 | SL+Target | 4/6 | 11.8 | 317.75 | 61.35 | 1.2 | 0.03 | AMD,AVGO,INTC,MS |
| fixed_sl0.05_rr2 | SL+Target | 4/6 | 11.52 | 318.0 | 61.37 | 1.2 | 0.03 | AMD,AVGO,INTC,MS |
| fixed_sl0.05_rr2.2 | SL+Target | 4/6 | 11.47 | 317.75 | 61.35 | 1.2 | 0.03 | AMD,AVGO,INTC,MS |
| fixed_sl0.05_rr1.5 | SL+Target | 4/6 | 10.73 | 318.25 | 61.4 | 1.18 | 0.02 | AMD,AVGO,INTC,MS |
| fixed_tr0.05 | 只Trailing | 3/6 | 17.58 | 302.33 | 60.74 | 1.31 | None | AVGO,INTC,MS |

### ma_crossover

| 出場組合 | 型 | 通過檔數 | 平均OOS EV | 平均交易 | 勝率% | PF | 平均R | 通過檔 |
|---|---|---|---|---|---|---|---|---|
| **baseline** | 訊號出場 | 4/6 | 21.71 | 337.5 | 31.21 | 1.25 | None | AMD,INTC,ORCL,MS |
| fixed_sl0.05_rr4 | SL+Target | 3/6 | 25.8 | 335.33 | 32.99 | 1.28 | 0.05 | AMD,INTC,MS |
| fixed_sl0.05 | 只SL | 3/6 | 25.05 | 335.33 | 32.99 | 1.27 | 0.05 | AMD,INTC,MS |
| fixed_sl0.05_rr3 | SL+Target | 3/6 | 24.71 | 335.33 | 32.99 | 1.27 | 0.05 | AMD,INTC,MS |
| fixed_sl0.05_rr2.5 | SL+Target | 3/6 | 23.64 | 335.33 | 32.99 | 1.27 | 0.05 | AMD,INTC,MS |
| fixed_sl0.05_rr2.2 | SL+Target | 3/6 | 21.96 | 335.33 | 32.99 | 1.25 | 0.05 | AMD,INTC,MS |
| fixed_sl0.05_rr2 | SL+Target | 3/6 | 20.91 | 335.33 | 32.99 | 1.24 | 0.04 | AMD,INTC,MS |
| fixed_sl0.05_rr1.5 | SL+Target | 3/6 | 19.68 | 335.67 | 33.16 | 1.24 | 0.04 | AMD,INTC,MS |
| fixed_sl0.03 | 只SL | 3/6 | 18.52 | 335.33 | 32.21 | 1.21 | 0.07 | AMD,INTC,MS |

### momentum

| 出場組合 | 型 | 通過檔數 | 平均OOS EV | 平均交易 | 勝率% | PF | 平均R | 通過檔 |
|---|---|---|---|---|---|---|---|---|
| **baseline** | 訊號出場 | 3/6 | 179.8 | 37.0 | 46.29 | 1.84 | None | AMD,INTC,ORCL |
| fixed_sl0.05_rr2.2 | SL+Target | 3/6 | 94.56 | 55.0 | 39.77 | 1.41 | 0.19 | AMD,INTC,ORCL |
| swing20_rr4 | SL+Target | 3/6 | 89.25 | 49.0 | 34.06 | 1.35 | 0.21 | AMD,INTC,ORCL |
| swing20_rr2.5 | SL+Target | 3/6 | 88.1 | 52.33 | 36.74 | 1.36 | 0.17 | AMD,INTC,ORCL |
| swing20_rr3 | SL+Target | 3/6 | 84.84 | 50.33 | 35.9 | 1.37 | 0.16 | AMD,INTC,ORCL |
| swing20_rr2.2 | SL+Target | 3/6 | 79.29 | 54.33 | 36.91 | 1.32 | 0.14 | AMD,INTC,ORCL |
| fixed_sl0.05_rr2.5 | SL+Target | 3/6 | 76.37 | 52.33 | 37.98 | 1.32 | 0.15 | AMD,INTC,ORCL |
| swing20_rrNone | 只SL | 3/6 | 72.13 | 42.67 | 33.72 | 1.34 | 0.07 | AMD,INTC,ORCL |
| swing20_rr2 | SL+Target | 3/6 | 67.08 | 55.67 | 37.57 | 1.29 | 0.11 | AMD,INTC,ORCL |

## 15Min

### bollinger

| 出場組合 | 型 | 通過檔數 | 平均OOS EV | 平均交易 | 勝率% | PF | 平均R | 通過檔 |
|---|---|---|---|---|---|---|---|---|
| **baseline** | 訊號出場 | 5/6 | 38.25 | 128.8 | 65.68 | 1.45 | None | AMD,AVGO,INTC,BAC,MS |
| swing20_rrNone | 只SL | 6/6 | 15.11 | 179.83 | 43.48 | 1.22 | -0.87 | AMD,AVGO,INTC,ORCL,BAC,MS |
| swing20_rr4 | SL+Target | 6/6 | 14.45 | 180.5 | 45.18 | 1.21 | -0.79 | AMD,AVGO,INTC,ORCL,BAC,MS |
| swing20_rr3 | SL+Target | 6/6 | 13.76 | 180.5 | 45.46 | 1.2 | -0.82 | AMD,AVGO,INTC,ORCL,BAC,MS |
| fixed_sl0.03 | 只SL | 5/6 | 25.28 | 167.2 | 60.56 | 1.32 | 0.09 | AMD,AVGO,INTC,BAC,MS |
| fixed_sl0.05_rr3 | SL+Target | 5/6 | 24.77 | 146.0 | 64.75 | 1.28 | 0.05 | AMD,AVGO,INTC,BAC,MS |
| fixed_sl0.05 | 只SL | 5/6 | 24.45 | 146.0 | 64.75 | 1.27 | 0.05 | AMD,AVGO,INTC,BAC,MS |
| fixed_sl0.05_rr4 | SL+Target | 5/6 | 24.45 | 146.0 | 64.75 | 1.27 | 0.05 | AMD,AVGO,INTC,BAC,MS |
| swing20_rr2.5 | SL+Target | 5/6 | 15.84 | 177.8 | 46.4 | 1.24 | -0.87 | AMD,AVGO,INTC,BAC,MS |

### ma_crossover

| 出場組合 | 型 | 通過檔數 | 平均OOS EV | 平均交易 | 勝率% | PF | 平均R | 通過檔 |
|---|---|---|---|---|---|---|---|---|
| **baseline** | 訊號出場 | 5/6 | 53.65 | 163.8 | 36.12 | 1.49 | None | AMD,AVGO,INTC,ORCL,MS |
| fixed_sl0.05_rr4 | SL+Target | 5/6 | 54.88 | 164.0 | 35.94 | 1.49 | 0.1 | AMD,AVGO,INTC,ORCL,MS |
| fixed_sl0.05 | 只SL | 5/6 | 46.35 | 163.8 | 35.83 | 1.42 | 0.09 | AMD,AVGO,INTC,ORCL,MS |
| fixed_sl0.05_rr3 | SL+Target | 5/6 | 45.87 | 164.0 | 35.94 | 1.43 | 0.08 | AMD,AVGO,INTC,ORCL,MS |
| fixed_sl0.05_rr2.2 | SL+Target | 5/6 | 44.86 | 164.4 | 36.16 | 1.42 | 0.08 | AMD,AVGO,INTC,ORCL,MS |
| fixed_sl0.05_rr2.5 | SL+Target | 5/6 | 44.18 | 164.2 | 36.06 | 1.42 | 0.08 | AMD,AVGO,INTC,ORCL,MS |
| fixed_sl0.05_rr1.5 | SL+Target | 5/6 | 37.07 | 171.4 | 36.91 | 1.37 | 0.07 | AMD,AVGO,INTC,BAC,MS |
| fixed_sl0.03 | 只SL | 5/6 | 30.19 | 164.0 | 34.04 | 1.28 | 0.1 | AMD,AVGO,INTC,ORCL,MS |
| swing20_rr2.5 | SL+Target | 5/6 | 21.63 | 171.4 | 34.48 | 1.22 | 0.04 | AMD,AVGO,INTC,BAC,MS |

### rsi

| 出場組合 | 型 | 通過檔數 | 平均OOS EV | 平均交易 | 勝率% | PF | 平均R | 通過檔 |
|---|---|---|---|---|---|---|---|---|
| **baseline** | 訊號出場 | 5/6 | 24.1 | 226.0 | 65.73 | 1.28 | None | AMD,AVGO,INTC,BAC,MS |
| fixed_sl0.05_rr2.5 | SL+Target | 4/6 | 18.33 | 197.5 | 65.28 | 1.18 | 0.04 | AVGO,INTC,BAC,MS |
| fixed_sl0.05_rr2.2 | SL+Target | 4/6 | 18.26 | 197.5 | 65.28 | 1.18 | 0.04 | AVGO,INTC,BAC,MS |
| fixed_sl0.05_rr3 | SL+Target | 4/6 | 17.84 | 197.25 | 65.25 | 1.17 | 0.04 | AVGO,INTC,BAC,MS |
| fixed_sl0.05 | 只SL | 4/6 | 17.73 | 197.25 | 65.25 | 1.17 | 0.04 | AVGO,INTC,BAC,MS |
| fixed_sl0.05_rr4 | SL+Target | 4/6 | 17.73 | 197.25 | 65.25 | 1.17 | 0.04 | AVGO,INTC,BAC,MS |
| fixed_sl0.05_rr2 | SL+Target | 4/6 | 17.53 | 197.5 | 65.28 | 1.17 | 0.04 | AVGO,INTC,BAC,MS |
| fixed_sl0.05_rr1.5 | SL+Target | 4/6 | 14.87 | 198.0 | 65.25 | 1.15 | 0.03 | AVGO,INTC,BAC,MS |
| fixed_sl0.03 | 只SL | 3/6 | 19.31 | 240.67 | 60.84 | 1.2 | 0.07 | AVGO,INTC,MS |

## 30Min

### adx_trend

| 出場組合 | 型 | 通過檔數 | 平均OOS EV | 平均交易 | 勝率% | PF | 平均R | 通過檔 |
|---|---|---|---|---|---|---|---|---|
| **baseline** | 訊號出場 | 6/6 | 51.83 | 109.67 | 43.61 | 1.48 | None | AMD,AVGO,INTC,ORCL,BAC,MS |
| swing20_rrNone | 只SL | 6/6 | 29.14 | 121.5 | 37.94 | 1.29 | 0.04 | AMD,AVGO,INTC,ORCL,BAC,MS |
| fixed_sl0.05 | 只SL | 6/6 | 27.93 | 112.83 | 41.46 | 1.23 | 0.06 | AMD,AVGO,INTC,ORCL,BAC,MS |
| fixed_sl0.05_rr4 | SL+Target | 6/6 | 27.76 | 114.0 | 41.2 | 1.23 | 0.06 | AMD,AVGO,INTC,ORCL,BAC,MS |
| swing20_rr2 | SL+Target | 6/6 | 25.81 | 139.33 | 40.26 | 1.27 | 0.02 | AMD,AVGO,INTC,ORCL,BAC,MS |
| swing20_rr2.5 | SL+Target | 6/6 | 25.4 | 133.67 | 39.25 | 1.27 | 0.01 | AMD,AVGO,INTC,ORCL,BAC,MS |
| swing20_rr3 | SL+Target | 6/6 | 25.39 | 132.67 | 38.92 | 1.27 | 0.02 | AMD,AVGO,INTC,ORCL,BAC,MS |
| swing20_rr4 | SL+Target | 6/6 | 25.28 | 128.67 | 38.41 | 1.26 | 0.03 | AMD,AVGO,INTC,ORCL,BAC,MS |
| swing20_rr2.2 | SL+Target | 6/6 | 25.16 | 137.67 | 39.43 | 1.27 | 0.01 | AMD,AVGO,INTC,ORCL,BAC,MS |

### bollinger

| 出場組合 | 型 | 通過檔數 | 平均OOS EV | 平均交易 | 勝率% | PF | 平均R | 通過檔 |
|---|---|---|---|---|---|---|---|---|
| **baseline** | 訊號出場 | 6/6 | 100.53 | 64.17 | 64.47 | 2.18 | None | AMD,AVGO,INTC,ORCL,BAC,MS |
| swing20_rr4 | SL+Target | 6/6 | 60.19 | 81.5 | 49.59 | 1.82 | -1.62 | AMD,AVGO,INTC,ORCL,BAC,MS |
| swing20_rrNone | 只SL | 5/6 | 86.07 | 79.2 | 48.19 | 2.15 | -0.95 | AMD,AVGO,INTC,BAC,MS |
| swing20_rr3 | SL+Target | 5/6 | 71.63 | 79.8 | 49.98 | 1.97 | -1.88 | AMD,AVGO,INTC,BAC,MS |
| swing20_rr2.5 | SL+Target | 5/6 | 70.82 | 79.8 | 50.21 | 1.96 | -1.9 | AMD,AVGO,INTC,BAC,MS |
| swing20_rr2.2 | SL+Target | 5/6 | 69.92 | 79.6 | 50.32 | 1.95 | -1.96 | AMD,AVGO,INTC,BAC,MS |
| swing20_rr2 | SL+Target | 5/6 | 69.9 | 79.6 | 50.8 | 1.95 | -1.94 | AMD,AVGO,INTC,BAC,MS |
| swing20_rr1.5 | SL+Target | 5/6 | 68.74 | 79.6 | 51.28 | 1.93 | -1.99 | AMD,AVGO,INTC,BAC,MS |
| fixed_sl0.05 | 只SL | 5/6 | 55.67 | 76.4 | 58.62 | 1.48 | 0.1 | AMD,AVGO,INTC,BAC,MS |

### donchian

| 出場組合 | 型 | 通過檔數 | 平均OOS EV | 平均交易 | 勝率% | PF | 平均R | 通過檔 |
|---|---|---|---|---|---|---|---|---|
| **baseline** | 訊號出場 | 6/6 | 54.03 | 93.67 | 44.44 | 1.41 | None | AMD,AVGO,INTC,ORCL,BAC,MS |
| fixed_sl0.05_rr4 | SL+Target | 6/6 | 53.07 | 96.5 | 43.71 | 1.4 | 0.11 | AMD,AVGO,INTC,ORCL,BAC,MS |
| fixed_sl0.05_rr2.5 | SL+Target | 6/6 | 50.91 | 102.67 | 42.94 | 1.36 | 0.1 | AMD,AVGO,INTC,ORCL,BAC,MS |
| fixed_sl0.05_rr2.2 | SL+Target | 6/6 | 49.7 | 103.5 | 43.45 | 1.36 | 0.1 | AMD,AVGO,INTC,ORCL,BAC,MS |
| fixed_sl0.05_rr3 | SL+Target | 6/6 | 48.64 | 99.33 | 43.0 | 1.36 | 0.1 | AMD,AVGO,INTC,ORCL,BAC,MS |
| fixed_sl0.05 | 只SL | 6/6 | 48.28 | 95.17 | 43.65 | 1.37 | 0.1 | AMD,AVGO,INTC,ORCL,BAC,MS |
| fixed_sl0.05_rr2 | SL+Target | 6/6 | 47.43 | 105.33 | 43.69 | 1.35 | 0.1 | AMD,AVGO,INTC,ORCL,BAC,MS |
| swing20_rrNone | 只SL | 6/6 | 45.23 | 97.33 | 42.65 | 1.37 | 0.19 | AMD,AVGO,INTC,ORCL,BAC,MS |
| swing20_rr4 | SL+Target | 6/6 | 43.71 | 104.33 | 41.57 | 1.33 | 0.22 | AMD,AVGO,INTC,ORCL,BAC,MS |

## 1Hour

### bollinger

| 出場組合 | 型 | 通過檔數 | 平均OOS EV | 平均交易 | 勝率% | PF | 平均R | 通過檔 |
|---|---|---|---|---|---|---|---|---|
| **baseline** | 訊號出場 | 6/6 | 212.14 | 31.0 | 69.11 | 2.43 | None | AMD,AVGO,INTC,ORCL,BAC,MS |
| swing20_rrNone | 只SL | 6/6 | 189.31 | 34.67 | 59.67 | 2.42 | 2.54 | AMD,AVGO,INTC,ORCL,BAC,MS |
| swing20_rr4 | SL+Target | 6/6 | 175.59 | 34.83 | 60.77 | 2.3 | -0.39 | AMD,AVGO,INTC,ORCL,BAC,MS |
| swing20_rr2.5 | SL+Target | 6/6 | 175.14 | 34.83 | 61.27 | 2.35 | -0.61 | AMD,AVGO,INTC,ORCL,BAC,MS |
| swing20_rr2 | SL+Target | 6/6 | 174.76 | 34.83 | 61.81 | 2.34 | -0.22 | AMD,AVGO,INTC,ORCL,BAC,MS |
| swing20_rr2.2 | SL+Target | 6/6 | 174.35 | 34.83 | 61.27 | 2.34 | -0.68 | AMD,AVGO,INTC,ORCL,BAC,MS |
| swing20_rr3 | SL+Target | 6/6 | 173.8 | 34.83 | 60.77 | 2.28 | -0.57 | AMD,AVGO,INTC,ORCL,BAC,MS |
| fixed_tr0.05 | 只Trailing | 6/6 | 59.44 | 49.67 | 49.07 | 1.41 | None | AMD,AVGO,INTC,ORCL,BAC,MS |
| fixed_tr0.03 | 只Trailing | 6/6 | 29.95 | 61.0 | 42.43 | 1.28 | None | AMD,AVGO,INTC,ORCL,BAC,MS |

### ma_crossover

| 出場組合 | 型 | 通過檔數 | 平均OOS EV | 平均交易 | 勝率% | PF | 平均R | 通過檔 |
|---|---|---|---|---|---|---|---|---|
| **baseline** | 訊號出場 | 5/6 | 98.08 | 34.0 | 35.3 | 1.59 | None | AMD,INTC,ORCL,BAC,MS |
| swing20_rr2.2 | SL+Target | 6/6 | 37.82 | 45.33 | 37.72 | 1.28 | 0.17 | AMD,AVGO,INTC,ORCL,BAC,MS |
| fixed_sl0.05_rr3 | SL+Target | 5/6 | 69.8 | 48.2 | 37.08 | 1.44 | 0.14 | AMD,AVGO,ORCL,BAC,MS |
| swing20_rr3 | SL+Target | 5/6 | 65.87 | 49.0 | 36.71 | 1.49 | 0.25 | AVGO,INTC,ORCL,BAC,MS |
| fixed_sl0.05_rr4 | SL+Target | 5/6 | 63.04 | 35.0 | 34.14 | 1.43 | 0.12 | AMD,INTC,ORCL,BAC,MS |
| swing20_rr2.5 | SL+Target | 5/6 | 58.43 | 49.2 | 38.13 | 1.44 | 0.26 | AVGO,INTC,ORCL,BAC,MS |
| swing20_rr2 | SL+Target | 5/6 | 49.14 | 48.6 | 40.04 | 1.35 | 0.18 | AMD,AVGO,ORCL,BAC,MS |
| atr2.0_rrNone | 只SL | 5/6 | 31.35 | 35.6 | 27.65 | 1.31 | 0.26 | AMD,INTC,ORCL,BAC,MS |
| swing20_rrNone | 只SL | 4/6 | 102.59 | 36.5 | 36.56 | 1.68 | 0.47 | AMD,ORCL,BAC,MS |

### rsi

| 出場組合 | 型 | 通過檔數 | 平均OOS EV | 平均交易 | 勝率% | PF | 平均R | 通過檔 |
|---|---|---|---|---|---|---|---|---|
| **baseline** | 訊號出場 | 6/6 | 111.73 | 50.33 | 68.12 | 2.14 | None | AMD,AVGO,INTC,ORCL,BAC,MS |
| swing20_rrNone | 只SL | 6/6 | 74.31 | 73.33 | 48.14 | 1.8 | -0.34 | AMD,AVGO,INTC,ORCL,BAC,MS |
| swing20_rr4 | SL+Target | 6/6 | 71.34 | 74.0 | 49.65 | 1.77 | -0.29 | AMD,AVGO,INTC,ORCL,BAC,MS |
| swing20_rr3 | SL+Target | 6/6 | 71.09 | 74.17 | 50.85 | 1.77 | -0.28 | AMD,AVGO,INTC,ORCL,BAC,MS |
| swing20_rr2 | SL+Target | 6/6 | 69.77 | 74.67 | 52.94 | 1.77 | -0.32 | AMD,AVGO,INTC,ORCL,BAC,MS |
| swing20_rr2.5 | SL+Target | 6/6 | 68.51 | 74.33 | 51.23 | 1.75 | -0.35 | AMD,AVGO,INTC,ORCL,BAC,MS |
| swing20_rr2.2 | SL+Target | 6/6 | 67.97 | 74.67 | 52.06 | 1.75 | -0.34 | AMD,AVGO,INTC,ORCL,BAC,MS |
| swing20_rr1.5 | SL+Target | 6/6 | 67.3 | 75.33 | 54.88 | 1.76 | -0.34 | AMD,AVGO,INTC,ORCL,BAC,MS |
| fixed_sl0.05_rr3 | SL+Target | 5/6 | 59.47 | 68.0 | 60.45 | 1.41 | 0.13 | AMD,AVGO,INTC,BAC,MS |

## 2Hour

### bollinger

| 出場組合 | 型 | 通過檔數 | 平均OOS EV | 平均交易 | 勝率% | PF | 平均R | 通過檔 |
|---|---|---|---|---|---|---|---|---|
| **baseline** | 訊號出場 | 5/6 | 258.5 | 24.2 | 74.61 | 3.56 | None | AMD,AVGO,INTC,ORCL,MS |
| swing20_rr3 | SL+Target | 5/6 | 224.24 | 30.0 | 63.6 | 3.29 | -1.26 | AMD,AVGO,INTC,ORCL,MS |
| swing20_rr2.5 | SL+Target | 5/6 | 223.9 | 30.0 | 63.6 | 3.29 | -1.32 | AMD,AVGO,INTC,ORCL,MS |
| swing20_rr4 | SL+Target | 5/6 | 223.69 | 30.0 | 62.99 | 3.18 | -1.19 | AMD,AVGO,INTC,ORCL,MS |
| swing20_rr2.2 | SL+Target | 5/6 | 223.46 | 30.0 | 63.6 | 3.28 | -1.36 | AMD,AVGO,INTC,ORCL,MS |
| swing20_rr2 | SL+Target | 5/6 | 222.99 | 30.0 | 63.6 | 3.27 | -1.39 | AMD,AVGO,INTC,ORCL,MS |
| swing20_rr1.5 | SL+Target | 5/6 | 222.77 | 30.2 | 64.38 | 3.38 | -1.35 | AMD,AVGO,INTC,ORCL,MS |
| swing20_rrNone | 只SL | 5/6 | 218.4 | 30.0 | 60.49 | 3.14 | -1.86 | AMD,AVGO,INTC,ORCL,MS |
| fixed_sl0.03 | 只SL | 4/6 | 134.78 | 42.75 | 49.38 | 1.91 | 0.46 | AMD,AVGO,INTC,MS |

### donchian

| 出場組合 | 型 | 通過檔數 | 平均OOS EV | 平均交易 | 勝率% | PF | 平均R | 通過檔 |
|---|---|---|---|---|---|---|---|---|
| **baseline** | 訊號出場 | 5/6 | 191.51 | 30.2 | 41.41 | 1.86 | None | AMD,AVGO,INTC,ORCL,BAC |
| swing20_rr1.5 | SL+Target | 6/6 | 94.59 | 44.5 | 45.26 | 1.48 | 0.19 | AMD,AVGO,INTC,ORCL,BAC,MS |
| swing20_rrNone | 只SL | 5/6 | 192.58 | 30.6 | 40.92 | 1.88 | 0.56 | AMD,AVGO,INTC,ORCL,BAC |
| swing20_rr3 | SL+Target | 5/6 | 167.21 | 35.6 | 42.48 | 1.75 | 0.34 | AMD,AVGO,INTC,ORCL,BAC |
| swing20_rr4 | SL+Target | 5/6 | 165.36 | 33.0 | 43.1 | 1.8 | 0.33 | AMD,AVGO,INTC,ORCL,BAC |
| swing20_rr2.5 | SL+Target | 5/6 | 152.71 | 36.6 | 42.14 | 1.68 | 0.31 | AMD,AVGO,INTC,ORCL,BAC |
| swing20_rr2.2 | SL+Target | 5/6 | 143.33 | 37.8 | 44.11 | 1.68 | 0.26 | AMD,AVGO,INTC,ORCL,BAC |
| swing20_rr2 | SL+Target | 5/6 | 125.19 | 39.0 | 43.72 | 1.57 | 0.22 | AMD,AVGO,INTC,ORCL,BAC |
| fixed_tr0.03 | 只Trailing | 5/6 | 18.26 | 52.6 | 42.25 | 1.17 | None | AMD,INTC,ORCL,BAC,MS |

### rsi

| 出場組合 | 型 | 通過檔數 | 平均OOS EV | 平均交易 | 勝率% | PF | 平均R | 通過檔 |
|---|---|---|---|---|---|---|---|---|
| **baseline** | 訊號出場 | 5/6 | 272.11 | 26.2 | 72.9 | 3.34 | None | AMD,AVGO,INTC,ORCL,MS |
| swing20_rrNone | 只SL | 5/6 | 173.96 | 41.0 | 47.68 | 2.53 | -0.13 | AMD,AVGO,INTC,ORCL,MS |
| swing20_rr3 | SL+Target | 5/6 | 156.17 | 41.0 | 49.91 | 2.44 | -0.33 | AMD,AVGO,INTC,ORCL,MS |
| swing20_rr1.5 | SL+Target | 5/6 | 154.97 | 43.0 | 56.53 | 2.67 | -0.17 | AMD,AVGO,INTC,ORCL,MS |
| swing20_rr2.5 | SL+Target | 5/6 | 154.02 | 41.2 | 51.29 | 2.49 | -0.29 | AMD,AVGO,INTC,ORCL,MS |
| swing20_rr2 | SL+Target | 5/6 | 152.97 | 41.8 | 53.36 | 2.49 | -0.24 | AMD,AVGO,INTC,ORCL,MS |
| swing20_rr4 | SL+Target | 5/6 | 151.76 | 41.0 | 47.68 | 2.38 | -0.43 | AMD,AVGO,INTC,ORCL,MS |
| swing20_rr2.2 | SL+Target | 5/6 | 151.08 | 41.8 | 52.31 | 2.48 | -0.26 | AMD,AVGO,INTC,ORCL,MS |
| fixed_sl0.05 | 只SL | 5/6 | 125.36 | 44.0 | 59.31 | 1.65 | 0.26 | AMD,AVGO,INTC,BAC,MS |

## 4Hour

### macd

| 出場組合 | 型 | 通過檔數 | 平均OOS EV | 平均交易 | 勝率% | PF | 平均R | 通過檔 |
|---|---|---|---|---|---|---|---|---|
| **baseline** | 訊號出場 | 6/6 | 79.34 | 50.17 | 43.37 | 1.52 | None | AMD,AVGO,INTC,ORCL,BAC,MS |
| swing20_rr4 | SL+Target | 6/6 | 94.72 | 50.33 | 42.91 | 1.66 | 0.23 | AMD,AVGO,INTC,ORCL,BAC,MS |
| swing20_rr2 | SL+Target | 6/6 | 88.78 | 50.67 | 43.96 | 1.66 | 0.19 | AMD,AVGO,INTC,ORCL,BAC,MS |
| swing20_rr2.5 | SL+Target | 6/6 | 88.55 | 50.5 | 43.1 | 1.64 | 0.2 | AMD,AVGO,INTC,ORCL,BAC,MS |
| swing20_rr3 | SL+Target | 6/6 | 88.21 | 50.33 | 42.91 | 1.63 | 0.21 | AMD,AVGO,INTC,ORCL,BAC,MS |
| swing20_rrNone | 只SL | 6/6 | 87.43 | 50.17 | 42.07 | 1.6 | 0.19 | AMD,AVGO,INTC,ORCL,BAC,MS |
| swing20_rr2.2 | SL+Target | 6/6 | 85.05 | 50.5 | 43.1 | 1.61 | 0.18 | AMD,AVGO,INTC,ORCL,BAC,MS |
| swing20_rr1.5 | SL+Target | 6/6 | 74.91 | 50.83 | 44.53 | 1.59 | 0.14 | AMD,AVGO,INTC,ORCL,BAC,MS |
| fixed_sl0.05_rr4 | SL+Target | 6/6 | 74.73 | 50.67 | 41.26 | 1.45 | 0.15 | AMD,AVGO,INTC,ORCL,BAC,MS |

### rsi

| 出場組合 | 型 | 通過檔數 | 平均OOS EV | 平均交易 | 勝率% | PF | 平均R | 通過檔 |
|---|---|---|---|---|---|---|---|---|
| **baseline** | 訊號出場 | 5/6 | 213.9 | 25.4 | 74.1 | 4.44 | None | AMD,AVGO,INTC,ORCL,MS |
| swing20_rrNone | 只SL | 5/6 | 150.2 | 36.6 | 53.6 | 2.57 | -0.19 | AMD,AVGO,INTC,ORCL,MS |
| swing20_rr4 | SL+Target | 5/6 | 144.53 | 36.6 | 54.03 | 2.54 | -0.25 | AMD,AVGO,INTC,ORCL,MS |
| swing20_rr3 | SL+Target | 5/6 | 141.62 | 36.6 | 54.56 | 2.52 | -0.26 | AMD,AVGO,INTC,ORCL,MS |
| swing20_rr2.5 | SL+Target | 5/6 | 138.19 | 36.8 | 54.79 | 2.49 | -0.27 | AMD,AVGO,INTC,ORCL,MS |
| swing20_rr2.2 | SL+Target | 5/6 | 134.42 | 36.8 | 54.79 | 2.45 | -0.3 | AMD,AVGO,INTC,ORCL,MS |
| swing20_rr2 | SL+Target | 5/6 | 133.84 | 36.8 | 55.43 | 2.56 | -0.29 | AMD,AVGO,INTC,ORCL,MS |
| swing20_rr1.5 | SL+Target | 5/6 | 125.82 | 37.6 | 56.97 | 2.53 | -0.26 | AMD,AVGO,INTC,ORCL,MS |
| fixed_tr0.05 | 只Trailing | 5/6 | 29.4 | 52.6 | 47.11 | 1.18 | None | AMD,AVGO,INTC,ORCL,MS |

### williams_r

| 出場組合 | 型 | 通過檔數 | 平均OOS EV | 平均交易 | 勝率% | PF | 平均R | 通過檔 |
|---|---|---|---|---|---|---|---|---|
| **baseline** | 訊號出場 | 5/6 | 184.07 | 28.2 | 73.68 | 2.67 | None | AMD,AVGO,INTC,ORCL,MS |
| swing20_rrNone | 只SL | 5/6 | 108.67 | 46.8 | 48.48 | 2.01 | -0.15 | AMD,AVGO,INTC,ORCL,MS |
| swing20_rr3 | SL+Target | 5/6 | 95.13 | 47.8 | 50.28 | 1.93 | -0.27 | AMD,AVGO,INTC,ORCL,MS |
| swing20_rr4 | SL+Target | 5/6 | 93.65 | 47.0 | 49.09 | 1.9 | -0.32 | AMD,AVGO,INTC,ORCL,MS |
| swing20_rr2.5 | SL+Target | 5/6 | 93.16 | 47.8 | 50.69 | 1.93 | -0.31 | AMD,AVGO,INTC,ORCL,MS |
| swing20_rr2.2 | SL+Target | 5/6 | 92.95 | 48.0 | 51.26 | 1.93 | -0.32 | AMD,AVGO,INTC,ORCL,MS |
| swing20_rr2 | SL+Target | 5/6 | 90.75 | 48.2 | 51.95 | 1.93 | -0.31 | AMD,AVGO,INTC,ORCL,MS |
| swing20_rr1.5 | SL+Target | 5/6 | 83.83 | 48.6 | 52.31 | 1.88 | -0.38 | AMD,AVGO,INTC,ORCL,MS |
| atr2.0_rr2.2 | SL+Target | 4/6 | 62.62 | 48.5 | 56.23 | 1.32 | 0.15 | AMD,AVGO,INTC,MS |

## 1Day

### stochastic

| 出場組合 | 型 | 通過檔數 | 平均OOS EV | 平均交易 | 勝率% | PF | 平均R | 通過檔 |
|---|---|---|---|---|---|---|---|---|
| **baseline** | 訊號出場 | 5/6 | 82.61 | 43.0 | 47.92 | 1.53 | None | AMD,AVGO,INTC,ORCL,BAC |
| atr2.0_rr1.5 | SL+Target | 6/6 | 78.08 | 44.33 | 46.73 | 1.52 | 0.1 | AMD,AVGO,INTC,ORCL,BAC,MS |
| fixed_sl0.05_rr3 | SL+Target | 6/6 | 61.23 | 44.17 | 45.79 | 1.38 | 0.12 | AMD,AVGO,INTC,ORCL,BAC,MS |
| fixed_sl0.05_rr4 | SL+Target | 6/6 | 58.19 | 44.0 | 45.62 | 1.35 | 0.12 | AMD,AVGO,INTC,ORCL,BAC,MS |
| fixed_sl0.05 | 只SL | 6/6 | 55.43 | 44.0 | 45.62 | 1.34 | 0.11 | AMD,AVGO,INTC,ORCL,BAC,MS |
| atr2.0_rr2 | SL+Target | 5/6 | 103.6 | 43.4 | 48.32 | 1.67 | 0.14 | AMD,AVGO,INTC,ORCL,BAC |
| atr2.0_rr2.2 | SL+Target | 5/6 | 84.24 | 43.0 | 47.92 | 1.53 | 0.11 | AMD,AVGO,INTC,ORCL,BAC |
| atr2.0_rr2.5 | SL+Target | 5/6 | 83.58 | 43.0 | 47.92 | 1.53 | 0.11 | AMD,AVGO,INTC,ORCL,BAC |
| atr2.0_rrNone | 只SL | 5/6 | 80.65 | 43.0 | 47.92 | 1.51 | 0.11 | AMD,AVGO,INTC,ORCL,BAC |

