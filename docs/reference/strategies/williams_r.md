# 威廉指標策略（Williams %R）

> 註冊鍵：`williams_r` ｜ 類別：`WilliamsRStrategy` ｜ 檔案：`backend/strategies/williams_r.py`

## 這策略在做什麼

用 Williams %R 抓「超買 / 超賣」做反轉。概念跟 RSI 很像，只是數值範圍是
**-100 ~ 0**：收盤貼近近期最低就接近 -100（超賣），貼近最高就接近 0（超買）。
適合在區間盤裡逮反彈/回檔。

## 訊號邏輯

| 情況 | 訊號 | 白話原因 |
|------|------|----------|
| %R < 超賣線（預設 -80） | **BUY** | 收盤貼近近期低點，超賣，預期反彈 |
| %R > 超買線（預設 -20） | **SELL** | 收盤貼近近期高點，超買，預期回檔 |
| 中間 / 資料不足 / 無波動 | **HOLD** | 無明確訊號 |

## 參數

| 參數 | 預設值 | 說明 |
|------|--------|------|
| `period` | 14 | 回看幾天算高低點 |
| `overbought` | -20 | 高於此線視為超買→賣 |
| `oversold` | -80 | 低於此線視為超賣→買 |

## 怎麼算（純 pandas）

本專案只有 `close` 欄，故用 close 的 rolling 高低點近似標準的 high/low：

1. `highest = close.rolling(period).max()` 取近 period 最高
2. `lowest = close.rolling(period).min()` 取近 period 最低
3. `%R = (highest − 今收) / (highest − lowest) × -100`
4. 防呆：`highest == lowest`（價格無波動）直接 HOLD，避免除以 0。

## 注意 / 適用情境

- 適合：區間/盤整盤抓反轉。
- 不適合：強趨勢盤——%R 會長期黏在超買或超賣區，一直給反向訊號被巴。
- ⚠️ 績效看 **期望值 EV** 不是勝率；上線前先回測 + Paper 驗證，慎防過擬合。
