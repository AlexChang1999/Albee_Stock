---
name: strategy-builder
description: 把交易策略的描述/規則/數據，自動變成本專案能跑的策略模組（backend/strategies/<name>.py）+ 註冊 + 前端清單 + 文件 + 測試，一條龍落地並用 pytest 驗證。當使用者說「新增策略」「幫我做一個策略」「把這個交易員的策略寫成程式」「strategy builder」「產生策略」「實作 XX 指標策略」時觸發。
---

# 策略產生器（strategy-builder）

把一段「人類講的交易策略」變成本專案**能跑、能回測、已註冊**的策略模組。

## 鐵則（先讀，違反會出事）

- **純 pandas 自算指標**，不要用 ta-lib（Windows 裝不起來）。
- 策略**只決定訊號**：`generate_signal(df) -> (Signal.X, "中文原因")`，不下單、不碰 API。
- **資料不足先回 `Signal.HOLD`**，絕不對著太短的 df 算指標。
- 看績效用**期望值 EV**，不是勝率。產出的策略一律先回測 + Paper 驗證，慎防過度擬合。
- 完成後**強制驗證**：跑 `pytest` 綠 + `get_strategy('<name>', {})` 能實例化。

## 5 步流程（每步都要做，缺一不可）

新策略命名先定好（snake_case，例：`williams_r`），全程一致。命名規則見
[`references/how-to-register.md`](references/how-to-register.md)。

1. **產策略檔** `backend/strategies/<name>.py`
   - 複製 [`assets/strategy_template.py`](assets/strategy_template.py) 改寫。
   - 純 pandas 算指標；`generate_signal` 回 `(Signal.BUY/SELL/HOLD, 中文原因)`；
     開頭先擋資料不足回 HOLD。中文註解說明指標白話邏輯（仿 `rsi.py`）。

2. **註冊** `backend/strategies/__init__.py`
   - 加 1 行 import + 在 `STRATEGY_REGISTRY` 加 `"<name>": <Class>Strategy`。

3. **前端清單** `frontend/src/constants.js`
   - `STRATEGIES` 陣列加 `{ value: "<name>", label: "中文名" }`，`value` 必須==註冊鍵。

4. **文件** `docs/strategies/<name>.md`
   - 複製 [`assets/strategy_doc_template.md`](assets/strategy_doc_template.md) 填寫。
   - （`docs/strategies/` 若不存在就建。）

5. **測試** `tests/test_<name>.py`
   - 複製 [`assets/test_template.py`](assets/test_template.py) 改寫。
   - 至少 3 情境：**BUY / SELL / 資料不足→HOLD**；檔頭含 UTF-8 guard。

## 收尾驗證（一定要跑）

```powershell
venv\Scripts\python.exe -m pytest tests/test_<name>.py -q
venv\Scripts\python.exe -c "from backend.strategies import get_strategy; print(get_strategy('<name>', {}))"
```

兩個都過才算完成。

## 詳細參考（需要時才讀，省 Token）

- 6 個落地點 + 命名規則：[`references/how-to-register.md`](references/how-to-register.md)
- 避坑清單（過擬合 / EV>勝率 / 純 pandas / UTF-8 / 資料不足 HOLD）：[`references/common-pitfalls.md`](references/common-pitfalls.md)
- 程式骨架：[`assets/`](assets/)（`strategy_template.py`、`strategy_doc_template.md`、`test_template.py`）
