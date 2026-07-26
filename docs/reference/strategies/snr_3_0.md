# SNR 3.0 支撐阻力精準進場策略（Supply & Demand + Structure Confirmation）

> 註冊鍵：`snr_3_0` ｜ 類別：`Snr30Strategy` ｜ 檔案：`backend/strategies/snr_3_0.py`

## 這策略在做什麼

SNR 3.0 是「供需區 + 新鮮度過濾 + 多重確認」的支撐阻力策略。它不是看到前高前低
就畫線，而是找**尚未被多次回踩的關鍵區域（Fresh Zone）**，並要求該區域左側曾出現
**強烈價格爆發（Expansion / Engulfing）**——代表市場可能在該處留下機構資金痕跡。
價格第一次回踩該區時，需依序出現 **Rejection（拒絕）→ Confirmation（反轉確認）→
Structure Break（結構突破）**，三關全過才在當根發出訊號。

## 名詞定義（判定公式）

| 名詞 | 定義 |
|------|------|
| **Swing Low / High** | 左右各 `swing_window`(3) 根都更高/更低的局部極值。右側需 `swing_window` 根確認 → **延遲 3 根才認定**（用的是當下已知的歷史，合法、不偷看未來） |
| **Zone（供需區）** | 以 swing 價位為錨、寬度 `zone_atr_width`(0.5)×ATR(`atr_period`=14) 的區域；在近 `zone_lookback`(80) 根內尋找。支撐區 = [swing_low, swing_low + 寬度]；阻力區 = [swing_high − 寬度, swing_high] |
| **Touch（觸碰）** | K 棒 low/high 進入 zone ± `touch_tolerance_atr`(0.2)×ATR 範圍算觸碰；**連續 in-zone 的 K 棒合併算同一群**（一次觸碰） |
| **Fresh Zone** | zone 建立（爆發離開）後、到當前這波回踩**之前**，歷史觸碰群數 ≤ `max_touches`(1)。碰越多次越可能是流動性陷阱，不再新鮮 |
| **Expansion** | K 棒實體 > 近 `expansion_lookback`(20) 根平均實體 × `expansion_body_mult`(1.5)。多頭要陽線、空頭要陰線 |
| **Engulfing（吞噬）** | 前一根反向 K，當根實體完整包住前一根實體 |
| **Rejection（拒絕）** | 回踩 zone 的 K 棒，影線佔全距 ≥ `rejection_wick_ratio`(0.4)。支撐看**下影線**、阻力看**上影線** |
| **Confirmation（確認）** | Rejection 之後出現順向 K（陽/陰線）或順向吞噬 |
| **Structure Break** | 當根收盤突破前 `structure_break_lookback`(5) 根（不含當根）的最高點（多）/ 跌破最低點（空） |

## BUY 訊號流程（七步時序）

1. 價格下跌打出 swing low（右側 3 根確認後才「已知」）。
2. 以 swing low 建立需求區（demand zone）。
3. 價格以 **bullish Expansion 或 Bullish Engulfing** 強勢離開該區 → zone 有效。
4. 價格走遠，期間未回踩（保持 Fresh，歷史觸碰 ≤ max_touches）。
5. 價格**首次回踩** zone，出現下影線 Rejection。
6. 出現 Bullish Confirmation（陽線或多頭吞噬）。
7. **當根**收盤突破近 5 根小結構高點（Structure Break）→ 發出 BUY。

回傳：`(Signal.BUY, "SNR 3.0 多頭：Fresh Support 回踩 + 拒絕 + 多頭確認 + 結構突破（參考停損 X／目標 Y）")`

## SELL 訊號流程（完全鏡像）

swing high → supply zone → bearish Expansion / Bearish Engulfing 離開 → 保持 Fresh →
首次回抽 + 上影線 Rejection → Bearish Confirmation → 當根跌破近 5 根低點 → SELL。

## HOLD 條件

以下任一成立回 HOLD，原因用中文說明缺哪個條件：

- K 線資料不足（< zone_lookback + atr_period + swing_window + 1 根）或缺 high/low/open 欄。
- 找不到有效 Fresh Zone（無 swing、或左側無 Expansion/Engulfing）。
- Zone 已被觸碰太多次（stale）。
- 價格尚未回踩 Zone。
- 已回踩但無 Rejection；有 Rejection 但無 Confirmation；有 Confirmation 但結構未突破。

## 參數（與 `STRATEGY_PARAM_SPECS` 一字不差）

| 參數 | 預設 | 範圍 | 控制什麼 |
|------|------|------|----------|
| `zone_lookback` | 80 | 20–250 | 往回幾根找 swing / zone |
| `swing_window` | 3 | 2–10 | swing 左右各幾根確認 |
| `atr_period` | 14 | 5–50 | ATR 週期 |
| `zone_atr_width` | 0.5 | 0.1–2.0 | zone 寬度 = 此值 × ATR |
| `touch_tolerance_atr` | 0.2 | 0.05–1.0 | 觸碰判定容忍 = 此值 × ATR |
| `max_touches` | 1 | 1–3 | 歷史觸碰群數超過即不 Fresh |
| `expansion_body_mult` | 1.5 | 1.0–3.0 | Expansion 實體倍數門檻 |
| `expansion_lookback` | 20 | 5–60 | 平均實體的回看根數 |
| `rejection_wick_ratio` | 0.4 | 0.2–0.8 | 影線/全距最小比例 |
| `structure_break_lookback` | 5 | 2–20 | 結構突破回看根數 |
| `reward_r` | 2.0 | 1.0–5.0 | 目標價 = 進場 ± 此值 × R（寫進 reason 供參考） |
| `atr_buffer` | 0.2 | 0.0–1.0 | 停損緩衝 = 此值 × ATR（寫進 reason 供參考） |
| `allow_short` | True | — | False 時不產 SELL 開空訊號（不進參數網格） |

## 出場語意與 reward_r / atr_buffer 的角色

- 參考停損 = zone 外緣 ∓ `atr_buffer`×ATR；參考目標 = 進場價 ± `reward_r`×(進場−停損)。
- v1 是無狀態 `BaseStrategy`：**stop/target 只算出來寫進 reason 供人看**，不由策略執行。
- 實際出場 = 反向訊號，或回測時帶引擎風控參數近似括號單，例如
  `stop_loss_pct`/`take_profit_pct` 設成約 1R/2R 對應的百分比。

## v1 範圍界線（刻意不做）

- **單一 OHLCV DataFrame、日線可回測**。不做真 H4/M30/M1 多時間框架——那需要
  intraday 多框架資料對齊與更細的回測（v2 方向）。原始策略的「H4 找 Zone、M30 看
  Expansion、M1 找 BO」在 v1 用同一框架的參數化邏輯近似。
- **必須有 open/high/low 欄**：影線/吞噬/實體判定離不開它們，缺欄回 HOLD（不像其他
  策略可退化 close-only）。
- SELL 訊號在回測 `allow_short=True` 下 = 開空評估；**實盤 Bot 不支援做空**，SELL 只平多。

## 防偷看未來聲明

- 所有判定只用「已收盤的 K 棒」；swing 的右側確認延遲 `swing_window` 根屬合法延遲。
- 訊號於當根收盤產生，由回測引擎於**次根開盤**成交（含手續費/滑價）。
- 不可先看到後面大漲，再回頭說前面是支撐——每根只用當下以前的資料判斷。

## 注意 / 適用情境

- 適合：有明確波段結構、回踩行為乾淨的標的（大盤 ETF：SPY/QQQ 先驗證）。
- 不適合：低波動黏著盤（zone 判定失真）、單邊暴走不回踩的行情（永遠等不到進場）。
- 條件多、訊號稀疏是特性不是 bug——回測 0 交易才是死策略，要用 SPY 365+ 天實跑確認。
- ⚠️ 績效看 **期望值 EV / 樣本外 OOS** 不是勝率；上線前先回測 + Paper 驗證，慎防過擬合。
