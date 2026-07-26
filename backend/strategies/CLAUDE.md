# backend/strategies/ 策略開發合約

> 進到這個資料夾實作/修改策略前必讀的速查合約。一條龍新增策略請走
> `.claude/skills/strategy-builder/` skill；本檔只放「合約 + 鐵則 + 落地點 + 驗證」，
> 細節見 skill 的 `references/`（不在此重複）。

## 資料夾定位

- 每策略一檔、鬆耦合，可獨立新增/修改/停用。
- 策略**只產訊號**，不下單、不碰 API、不管部位——成交與資金由回測引擎/實盤 Bot 負責。

## BaseStrategy 合約

- 繼承 `base.py` 的 `BaseStrategy`，覆寫 `name`（== 註冊鍵，snake_case）。
- 實作 `generate_signal(df) -> tuple[str, str]`：回 `(Signal.BUY/SELL/HOLD, "中文原因")`。
- `df` 時間**舊→新**，最新一根是 `df.iloc[-1]`；可能只有 `close` 欄（測試資料）——
  能退回 close 就退回，真的需要 high/low/open 的策略缺欄時回 HOLD 並在文件註明。
- **資料不足一律先 `return Signal.HOLD, "資料不足（需要至少 X 筆）"`，絕不丟例外。**
- 參數一律 `self.params.get("鍵", 預設)`；**預設值必須 == `__init__.py` 的
  `STRATEGY_PARAM_SPECS` default**。鍵名打錯會靜默回退預設值不報錯（本專案已知地雷）。
- 有狀態的進出場邏輯（續抱/持倉根數）→ 改繼承 `ScriptStrategy`（`on_bar` + ctx），
  成交仍走同一核心，不分岔。

## 防偷看未來鐵則（違反 = 回測 EV 造假）

- 回測引擎經 `produce_signals` 逐根切片：`generate_signal` 只拿得到「到第 i 根為止」的 df。
  策略內**只能用當下以前的資料**，不可假設後面還有 K 棒。
- 訊號於第 i 根收盤算出 → 引擎於第 i+1 根**開盤價**成交；策略不碰成交價。
- 「右側確認」類結構（swing high/low 需右邊 N 根確認）**延遲 N 根才認定 = 合法**
  （那是當下已知的歷史）；用未來根回頭確認當根 = 違規。

## 新策略的 6 個落地點

| # | 檔案 | 做什麼 | 漏了的症狀 |
|---|------|--------|------------|
| 1 | `strategies/<name>.py` | 策略本體 | — |
| 2 | `strategies/__init__.py` | **四處**：import、`STRATEGY_REGISTRY`、`STRATEGY_LABELS`、`STRATEGY_PARAM_SPECS` | 漏 REGISTRY 直接 ValueError；漏 LABELS 前端顯示代號；漏 PARAM_SPECS 探勘橋/LLM 生成器不認識參數 |
| 3 | `frontend/src/constants.js` | `STRATEGIES` 加 `{value, label}`（value == 註冊鍵） | 前端下拉選不到 |
| 4 | `docs/reference/strategies/<name>.md` | 策略文件 | 人與 AI 都查不到規格 |
| 5 | `tests/test_<name>.py` | 測試（扁平 `tests/`，勿建子夾） | 無護欄 |
| 6 | 選配：`lookback.py` 的 `min_bars_required` 加分支；`optimizer.py` `PARAM_GRIDS` 加網格 | 回看天數 / 自動海選 | 漏 lookback 且需求 > 60 根 → 實盤抓太少永遠 HOLD（靜默失準）；漏 PARAM_GRIDS 只是進不了海選 |

命名鐵律：`name` 屬性 == 註冊鍵 == constants `value` == doc 檔名，全程 snake_case。

## 技術規範

- **純 pandas 自算指標**（rolling/ewm/diff/clip），禁 ta-lib（Windows 裝不起來）。
- 中文註解密度仿 `rsi.py`；docstring 開頭白話講策略在看什麼。
- float 比較別用 `==`；比率分母可能為 0（一字線 high==low）要防除零。

## 測試最低要求

- 至少三情境：**BUY / SELL / 資料不足→HOLD**；合成資料要「必然」觸發訊號（手構 K 棒
  序列，不用隨機數）。
- 測試檔開頭 UTF-8 guard（`sys.stdout.reconfigure(encoding="utf-8")`，Windows cp950 會炸）
  + `sys.path.insert` 加專案根。
- 跨多根時序 pattern 的策略，加一條「截短資料應回 HOLD」驗不提早發訊。

## 驗證標準流程（完成前一定要跑）

```powershell
venv\Scripts\python.exe -m pytest tests/test_<name>.py -q
venv\Scripts\python.exe -c "from backend.strategies import get_strategy; print(get_strategy('<name>', {}))"
```

再用**大盤 ETF 實跑回測**確認策略活著（0 交易 = 死策略，測試全綠也沒用）：

```powershell
venv\Scripts\python.exe -c "from backend.services.backtest_engine import run_backtest; r = run_backtest('<name>', 'SPY', days=365); print(r['num_trades'], r['expected_value'])"
```

SPY 跑完換 QQQ 對照。看績效用**期望值 EV / 樣本外 OOS**，不是勝率。

## 做空語意（2026-07 起）

- 回測引擎 `run_backtest(..., allow_short=True)` 時：SELL 空手 → 開空、BUY 有空 → 回補；
  預設 `allow_short=False` 維持「SELL 只平多」。
- **實盤 Bot 只做多**——做空僅供回測評估，策略文件要註明。
