# 落地點與命名規則

一個策略要「完整存在」，必須同時碰到 **6 個地方**。少碰一個就會出怪事
（前端選得到但後端不認、或測試抓不到、或文件對不上）。

## 6 個落地點

| # | 檔案 | 做什麼 | 漏了會怎樣 |
|---|------|--------|-----------|
| 1 | `backend/strategies/<name>.py` | 策略本體，定義 `<Class>Strategy` | 沒策略可用 |
| 2 | `backend/strategies/__init__.py` | **四處**：import、`STRATEGY_REGISTRY`、`STRATEGY_LABELS`、`STRATEGY_PARAM_SPECS` | 漏 REGISTRY 報「未知的策略」；漏 LABELS 前端顯示代號；漏 PARAM_SPECS 探勘橋/LLM 生成器不認識參數 |
| 3 | `frontend/src/constants.js` | `STRATEGIES` 加 `{value,label}` | 前端下拉選單看不到 |
| 4 | `docs/reference/strategies/<name>.md` | 策略說明文件 | 別人看不懂這策略在幹嘛 |
| 5 | `tests/test_<name>.py` | BUY/SELL/資料不足 三情境測試 | 沒測試保護，改壞不知道 |
| 6 | 選配：`lookback.py` 的 `min_bars_required` 加分支；`optimizer.py` `PARAM_GRIDS` 加網格 | 回看天數 / 自動海選 | 漏 lookback 且需求 > 60 根 → 實盤抓太少永遠 HOLD（靜默失準）；漏 PARAM_GRIDS 只是進不了海選 |

（本表與 [`backend/strategies/CLAUDE.md`](../../../../backend/strategies/CLAUDE.md) 的「6 個落地點」同一套，改一邊要同步另一邊。）

## 命名規則（最重要的一致性）

以「威廉指標 Williams %R」為例：

| 項目 | 寫法 | 範例 |
|------|------|------|
| 註冊鍵 / 檔名 / `value` / doc 檔名 | **snake_case** | `williams_r` |
| 類別名稱 | **PascalCase + `Strategy`** | `WilliamsRStrategy` |
| `name` 類別屬性 | **== 註冊鍵** | `name = "williams_r"` |
| 前端 `label` | 中文顯示名（隨意） | `"威廉指標"` |

**鐵律**：`name` 屬性、註冊鍵、`constants.js` 的 `value`、doc 檔名 **四者完全相同**。
不同就會「前端選了 A、後端找不到」。

撞名（已有同名策略）：在所有位置加 `_v2` 後綴，例 `rsi_v2` / `RSIv2Strategy`。

## 註冊範本（__init__.py 要加的四處，缺一不可）

```python
# 1) 檔案上方 import 區，加一行
from backend.strategies.williams_r import WilliamsRStrategy

# 2) STRATEGY_REGISTRY 字典裡，加一行
STRATEGY_REGISTRY = {
    # ...原本的...
    "williams_r": WilliamsRStrategy,   # <-- 鍵 == name 屬性
}

# 3) STRATEGY_LABELS 字典裡，加一行（GET /strategies 顯示名單一來源）
STRATEGY_LABELS = {
    # ...原本的...
    "williams_r": "威廉指標",
}

# 4) STRATEGY_PARAM_SPECS 字典裡，加參數 schema
#    default 必須 == 策略檔 params.get 的預設值，否則 LLM 探勘橋/參數驗證會靜默漂移
STRATEGY_PARAM_SPECS = {
    # ...原本的...
    "williams_r": {
        "period": {"default": 14, "min": 2, "max": 100},
    },
}
```
