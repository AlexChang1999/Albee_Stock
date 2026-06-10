# 如何新增一個交易策略（操作指南）

> 給未來的你（或 AI）：在本軟體實際「加一個策略」要動哪些地方、怎麼用、怎麼驗。
> 策略**鬆耦合**——只決定買賣訊號，不下單、不碰 API。

## 兩條路

### 路徑 1（推薦、自動）：`strategy-builder` skill
對 Claude Code 說「**新增策略：<你的規則描述>**」（或「幫我做一個 XX 指標策略」）即觸發。
它會一條龍做完落地 + 跑 `pytest` 驗證，省去手動。詳見 `.claude/skills/strategy-builder/`。

### 路徑 2（手動）：自己改 5～6 個落地點

命名先定好（snake_case，例 `williams_r`），全程一致。

1. **策略檔** `backend/strategies/<name>.py`
   - 繼承 `base.py` 的 `BaseStrategy`；**純 pandas 自算指標**（不要 ta-lib，Windows 裝不起來）。
   - `generate_signal(df) -> (Signal.BUY/SELL/HOLD, "中文原因")`；**開頭先擋資料不足回 `Signal.HOLD`**。
   - 仿 `rsi.py` 的中文註解密度。
2. **註冊** `backend/strategies/__init__.py`
   - 加 1 行 `import` + 在 `STRATEGY_REGISTRY` 加 `"<name>": <Class>Strategy`；`STRATEGY_LABELS` 加中文顯示名。
3. **前端清單** `frontend/src/constants.js` 的 `STRATEGIES`
   - 加 `{ value: "<name>", label: "中文名" }`；`value` **必須等於註冊鍵**。
4. **文件** `docs/reference/strategies/<name>.md`（資料夾不存在就建）。
5. **測試** `tests/test_<name>.py`
   - 至少 3 情境：**BUY / SELL / 資料不足→HOLD**；檔頭加 UTF-8 guard（見其他測試）。
6. **（選配，但很重要）回看天數 + 自動海選/自適應**
   - `backend/strategies/lookback.py`：若策略有「週期」類參數，補上推算回看天數的規則，
     否則實盤/回測抓的資料可能不夠、靜默失準。
   - `backend/services/optimizer.py` 的 `PARAM_GRIDS`：**想讓新策略進「模式 B 自動海選」與
     「Phase 7 自適應對照表」就一定要加**它的參數網格；不加的話 `run_auto_backtest` / screener /
     step-03 對照表都掃不到它（只能手動建 Bot 用）。

## 加完怎麼「實際使用」

| 想做 | 怎麼用 |
|------|--------|
| 手動跑一隻 Bot | 前端「建立 Bot」表單選新策略 → 啟動（**預設 Paper 模擬**） |
| 回測 / 工作台 | 策略工作台選它跑回測、存 preset、看 EV 歷史 |
| 自動部署（模式 B） | 已加 `PARAM_GRIDS` → 盤前海選會自動評估它，過 **OOS EV + 勝率**門檻才部署 |
| 進自適應（step-03） | 已加 `PARAM_GRIDS` → 建對照表時納入各市場狀態的策略競爭 |

## 收尾驗證（一定要跑）

```powershell
venv\Scripts\python.exe -m pytest tests/test_<name>.py -q
venv\Scripts\python.exe -c "from backend.strategies import get_strategy; print(get_strategy('<name>', {}))"
```

兩個都過才算完成。**看績效一律用期望值 EV、看樣本外（OOS），不要只看勝率**（見
[`docs/ai-implementation-guardrails.md`](../ai-implementation-guardrails.md) 第伍節）。

## 新策略值不值得上線？

新增不等於有用。要證明它在**樣本外**真的賺，跑回測看 OOS EV；若要和既有層比較加分，
用 Phase 7 step-07 的驗證框架（`scripts/validate_layers.py` / `backend/services/validation.py`）。
**加不了分就別上線**——這是本專案的虧錢防線。
