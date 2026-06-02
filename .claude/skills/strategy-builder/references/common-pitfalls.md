# 避坑清單（寫策略最常踩的雷）

## 1. 過度擬合（Overfitting）— 最危險

- 「一週勝率 90%+」幾乎都是過擬合的陷阱：小賺很多次、一次大賠全吐回去。
- 不要為了讓回測好看，把參數調到剛好貼合歷史某一段。
- 對策：參數用**常見預設值**（如 RSI 14、布林 20）；產出後**先回測 + Paper 驗證**，
  別直接信。

## 2. 用 EV（期望值）判好壞，不是勝率

- `EV/筆 = 勝率 × 平均賺 − 敗率 × 平均賠`。
- 勝率高 ≠ 賺錢。一個 40% 勝率但賺賠比 3:1 的策略，EV 遠勝 90% 勝率但賺賠比 1:5。
- 策略的「原因說明」可以提勝率，但心裡要清楚最後看的是 EV。

## 3. 一律純 pandas 自算指標

- **不要** `import talib`（Windows 裝不起來，這專案刻意避開）。
- RSI/MACD/布林/KD 全部用 pandas 的 `rolling` / `ewm` / `diff` / `clip` 自己算。
- 參考現成寫法：`backend/strategies/rsi.py`、`macd.py`、`bollinger.py`。

## 4. 資料不足一定先回 HOLD

- 算指標前先檢查 `len(df)`。需要 N 期就至少要 N（有些要 N+1，如 RSI 要 diff）。
- 資料不夠時 `return Signal.HOLD, f"資料不足（需要至少 X 筆）"`，
  **絕不**對太短的 df 硬算（會拿到 NaN 或 IndexError）。

## 5. Windows UTF-8 guard（測試檔必加）

主控台預設 cp950，印中文/emoji 會崩潰。**測試檔開頭**一定要：

```python
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass
```

策略檔本身不用（後端 `config.py` 已全域設過），但**獨立執行的測試/腳本要自己加**。

## 6. 訊號與回傳型別

- 回傳一定是 `tuple[str, str]` = `(Signal.X, "中文原因")`。
- 用 `Signal.BUY / Signal.SELL / Signal.HOLD` 常數，**不要**手寫字串 `"buy"`（打錯不會報錯，會靜默失效）。
- `df` 時間順序是**舊→新**，最新一根在 `df.iloc[-1]`。

## 7. 測試用合成資料要「能逼出訊號」

- 別用隨機數據測，要刻意設計能必然觸發 BUY / SELL 的序列。
- 例：測超賣 BUY → 給一路下跌的 close；測突破 BUY → 前面平、最後一根爆漲。
- 參考 `tests/test_strategies.py` 既有 12+ 個測試的構造手法。
