# 研究矩陣 Round 1 —— timeframe 海選（M6）

- 日期：2026-07-03；study_tag：`m6-round1-2026-07-03`
- 池：AMD, AVGO, BAC, INTC, MS, ORCL（6 檔）；回看 730 天；無 filter、預設出場（fixed_pct baseline）
- 守門（沿用 optimizer）：OOS 交易 ≥20、過擬合差距 ≤0.5、OOS EV>0
- 排名鍵：先「守門通過檔數」（普遍性）再「平均 OOS EV」（期望值）
- ⚠️ PDT：估計年交易 >150 次的日內組合，實盤 <$25k 受 PDT 限制（paper 不受影響）

## 1Min

| # | 策略 | 通過檔數 | 平均OOS EV | 平均OOS交易 | 平均勝率% | 平均Sharpe | 平均gap | 年交易估 | 通過檔 | 註 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | momentum | 4/6 | 247.51 | 27.75 | 46.38 | 0.95 | 0.17 | 19.43 | AMD,AVGO,INTC,ORCL | ★留 |
| 2 | bollinger | 1/6 | 1.85 | 999.0 | 56.96 | 0.29 | None | 699.3 | AVGO | ★留 ⚠️PDT |
| 3 | ma_crossover | 1/6 | 0.89 | 1551.0 | 30.11 | 0.27 | None | 1085.7 | AMD | ★留 ⚠️PDT |
| 4 | stochastic | 0/6 | None | None | None | None | None | None |  |  |
| 5 | donchian | 0/6 | None | None | None | None | None | None |  |  |
| 6 | macd | 0/6 | None | None | None | None | None | None |  |  |
| 7 | williams_r | 0/6 | None | None | None | None | None | None |  |  |
| 8 | adx_trend | 0/6 | None | None | None | None | None | None |  |  |
| 9 | rsi | 0/6 | None | None | None | None | None | None |  |  |

## 5Min

| # | 策略 | 通過檔數 | 平均OOS EV | 平均OOS交易 | 平均勝率% | 平均Sharpe | 平均gap | 年交易估 | 通過檔 | 註 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | ma_crossover | 4/6 | 21.71 | 337.5 | 31.21 | 0.87 | -9.6 | 247.5 | AMD,INTC,ORCL,MS | ★留 ⚠️PDT |
| 2 | bollinger | 4/6 | 19.76 | 300.0 | 61.95 | 0.7 | -0.76 | 214.72 | AMD,AVGO,INTC,MS | ★留 ⚠️PDT |
| 3 | momentum | 3/6 | 179.8 | 37.0 | 46.29 | 0.97 | -16.65 | 25.9 | AMD,INTC,ORCL | ★留 |
| 4 | donchian | 3/6 | 14.61 | 447.0 | 36.7 | 0.97 | -0.03 | 324.87 | AMD,INTC,MS | ⚠️PDT |
| 5 | adx_trend | 3/6 | 12.52 | 329.0 | 40.01 | 0.53 | 0.46 | 235.63 | AMD,INTC,MS | ⚠️PDT |
| 6 | rsi | 1/6 | 15.37 | 487.0 | 62.22 | 0.62 | None | 340.9 | INTC | ⚠️PDT |
| 7 | stochastic | 0/6 | None | None | None | None | None | None |  |  |
| 8 | macd | 0/6 | None | None | None | None | None | None |  |  |
| 9 | williams_r | 0/6 | None | None | None | None | None | None |  |  |

## 15Min

| # | 策略 | 通過檔數 | 平均OOS EV | 平均OOS交易 | 平均勝率% | 平均Sharpe | 平均gap | 年交易估 | 通過檔 | 註 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | ma_crossover | 5/6 | 53.53 | 163.6 | 36.06 | 1.05 | -1.49 | 120.04 | AMD,AVGO,INTC,ORCL,MS | ★留 |
| 2 | bollinger | 5/6 | 38.33 | 128.6 | 65.77 | 0.71 | -4.44 | 95.26 | AMD,AVGO,INTC,BAC,MS | ★留 |
| 3 | rsi | 5/6 | 23.62 | 225.4 | 65.82 | 0.49 | -13.68 | 164.7 | AMD,AVGO,INTC,BAC,MS | ★留 ⚠️PDT |
| 4 | adx_trend | 4/6 | 51.97 | 127.0 | 43.61 | 0.8 | -2.66 | 90.83 | AMD,INTC,ORCL,MS |  |
| 5 | donchian | 4/6 | 41.17 | 214.5 | 39.23 | 0.76 | -1.13 | 153.68 | AMD,INTC,ORCL,MS | ⚠️PDT |
| 6 | momentum | 3/6 | 185.54 | 31.0 | 48.84 | 1.03 | -2.4 | 21.7 | AMD,INTC,ORCL |  |
| 7 | williams_r | 3/6 | 6.51 | 545.33 | 64.26 | 0.29 | None | 381.8 | AMD,AVGO,INTC | ⚠️PDT |
| 8 | macd | 2/6 | 3.21 | 711.5 | 34.89 | 0.27 | None | 498.15 | INTC,ORCL | ⚠️PDT |
| 9 | stochastic | 0/6 | None | None | None | None | None | None |  |  |

## 30Min

| # | 策略 | 通過檔數 | 平均OOS EV | 平均OOS交易 | 平均勝率% | 平均Sharpe | 平均gap | 年交易估 | 通過檔 | 註 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | donchian | 6/6 | 54.11 | 93.67 | 44.44 | 0.91 | -0.2 | 70.1 | AMD,AVGO,INTC,ORCL,BAC,MS | ★留 |
| 2 | adx_trend | 6/6 | 52.83 | 109.67 | 43.61 | 0.86 | -4.89 | 80.82 | AMD,AVGO,INTC,ORCL,BAC,MS | ★留 |
| 3 | bollinger | 5/6 | 119.98 | 62.2 | 64.39 | 0.98 | -18.03 | 46.34 | AMD,AVGO,INTC,BAC,MS | ★留 |
| 4 | rsi | 5/6 | 56.85 | 96.6 | 67.49 | 0.76 | -21.75 | 71.78 | AMD,AVGO,INTC,BAC,MS |  |
| 5 | ma_crossover | 5/6 | 47.19 | 121.8 | 38.32 | 0.84 | -3.41 | 89.42 | AMD,AVGO,INTC,BAC,MS |  |
| 6 | macd | 4/6 | 20.83 | 341.0 | 37.54 | 0.74 | -4.84 | 248.28 | AMD,AVGO,INTC,MS | ⚠️PDT |
| 7 | momentum | 3/6 | 182.17 | 46.0 | 41.08 | 1.23 | -3.19 | 32.2 | AMD,INTC,ORCL |  |
| 8 | williams_r | 2/6 | 10.12 | 233.5 | 67.02 | 0.32 | None | 163.5 | AVGO,INTC | ⚠️PDT |
| 9 | stochastic | 0/6 | None | None | None | None | None | None |  |  |

## 1Hour

| # | 策略 | 通過檔數 | 平均OOS EV | 平均OOS交易 | 平均勝率% | 平均Sharpe | 平均gap | 年交易估 | 通過檔 | 註 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | bollinger | 6/6 | 210.52 | 31.0 | 69.11 | 0.8 | -3.76 | 23.05 | AMD,AVGO,INTC,ORCL,BAC,MS | ★留 |
| 2 | rsi | 6/6 | 107.48 | 50.17 | 67.68 | 0.67 | -0.57 | 37.2 | AMD,AVGO,INTC,ORCL,BAC,MS | ★留 |
| 3 | ma_crossover | 5/6 | 146.8 | 34.6 | 36.24 | 0.93 | -0.1 | 26.9 | AMD,INTC,ORCL,BAC,MS | ★留 |
| 4 | adx_trend | 5/6 | 139.37 | 32.6 | 41.35 | 0.82 | -11.24 | 23.5 | AMD,AVGO,INTC,ORCL,BAC |  |
| 5 | williams_r | 5/6 | 32.59 | 110.8 | 67.83 | 0.5 | None | 83.9 | AMD,AVGO,INTC,BAC,MS |  |
| 6 | momentum | 3/6 | 201.82 | 43.33 | 40.63 | 1.08 | -1.97 | 30.33 | AMD,INTC,ORCL |  |
| 7 | macd | 3/6 | 77.17 | 168.33 | 43.49 | 1.57 | -3.84 | 124.07 | AMD,INTC,MS |  |
| 8 | donchian | 2/6 | 243.39 | 36.0 | 46.06 | 1.22 | -0.5 | 25.2 | AMD,INTC |  |
| 9 | stochastic | 1/6 | 4.56 | 986.0 | 36.51 | 0.58 | None | 690.9 | AMD | ⚠️PDT |

## 2Hour

| # | 策略 | 通過檔數 | 平均OOS EV | 平均OOS交易 | 平均勝率% | 平均Sharpe | 平均gap | 年交易估 | 通過檔 | 註 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | rsi | 5/6 | 272.11 | 26.2 | 72.9 | 0.78 | -1.92 | 18.9 | AMD,AVGO,INTC,ORCL,MS | ★留 |
| 2 | bollinger | 5/6 | 258.5 | 24.2 | 74.61 | 0.7 | -1.8 | 17.58 | AMD,AVGO,INTC,ORCL,MS | ★留 |
| 3 | donchian | 5/6 | 192.74 | 30.0 | 41.56 | 0.75 | -0.66 | 21.64 | AMD,AVGO,INTC,ORCL,BAC | ★留 |
| 4 | williams_r | 5/6 | 90.15 | 59.0 | 71.49 | 0.74 | -1.01 | 43.8 | AMD,AVGO,INTC,BAC,MS |  |
| 5 | adx_trend | 3/6 | 347.68 | 31.67 | 44.89 | 1.12 | -1.4 | 22.17 | AMD,INTC,ORCL |  |
| 6 | momentum | 3/6 | 284.84 | 30.33 | 39.83 | 0.85 | -3.86 | 21.23 | AMD,INTC,ORCL |  |
| 7 | ma_crossover | 3/6 | 188.91 | 24.67 | 38.33 | 0.8 | -0.89 | 17.27 | AMD,INTC,ORCL |  |
| 8 | macd | 3/6 | 90.41 | 99.0 | 44.99 | 1.03 | -16.2 | 69.4 | AMD,AVGO,INTC |  |
| 9 | stochastic | 3/6 | 17.58 | 493.67 | 38.35 | 0.96 | -5.62 | 346.03 | AMD,AVGO,INTC | ⚠️PDT |

## 4Hour

| # | 策略 | 通過檔數 | 平均OOS EV | 平均OOS交易 | 平均勝率% | 平均Sharpe | 平均gap | 年交易估 | 通過檔 | 註 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | rsi | 5/6 | 213.9 | 25.4 | 74.1 | 0.65 | -0.9 | 18.4 | AMD,AVGO,INTC,ORCL,MS | ★留 |
| 2 | williams_r | 5/6 | 184.07 | 28.2 | 73.68 | 0.56 | -1.96 | 20.52 | AMD,AVGO,INTC,ORCL,MS | ★留 |
| 3 | macd | 5/6 | 87.5 | 49.4 | 44.63 | 0.7 | -0.59 | 35.9 | AMD,INTC,ORCL,BAC,MS | ★留 |
| 4 | adx_trend | 4/6 | 263.69 | 27.5 | 37.38 | 0.91 | -22.16 | 19.32 | AMD,INTC,ORCL,BAC |  |
| 5 | momentum | 3/6 | 400.06 | 24.0 | 38.69 | 1.02 | -1.01 | 16.87 | AMD,INTC,ORCL |  |
| 6 | donchian | 3/6 | 339.9 | 24.0 | 40.54 | 0.91 | -0.79 | 16.87 | AMD,INTC,ORCL |  |
| 7 | ma_crossover | 3/6 | 135.67 | 24.33 | 42.58 | 0.78 | 0.11 | 18.13 | AMD,INTC,MS |  |
| 8 | stochastic | 3/6 | 44.81 | 240.0 | 42.58 | 1.09 | -3.16 | 178.13 | AMD,INTC,MS | ⚠️PDT |
| 9 | bollinger | 0/6 | None | None | None | None | None | None |  |  |

## 1Day

| # | 策略 | 通過檔數 | 平均OOS EV | 平均OOS交易 | 平均勝率% | 平均Sharpe | 平均gap | 年交易估 | 通過檔 | 註 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | stochastic | 5/6 | 82.61 | 43.0 | 47.92 | 1.07 | -3.19 | 36.14 | AMD,AVGO,INTC,ORCL,BAC | ★留 |
| 2 | bollinger | 0/6 | None | None | None | None | None | None |  |  |
| 3 | rsi | 0/6 | None | None | None | None | None | None |  |  |
| 4 | momentum | 0/6 | None | None | None | None | None | None |  |  |
| 5 | williams_r | 0/6 | None | None | None | None | None | None |  |  |
| 6 | donchian | 0/6 | None | None | None | None | None | None |  |  |
| 7 | ma_crossover | 0/6 | None | None | None | None | None | None |  |  |
| 8 | macd | 0/6 | None | None | None | None | None | None |  |  |
| 9 | adx_trend | 0/6 | None | None | None | None | None | None |  |  |

