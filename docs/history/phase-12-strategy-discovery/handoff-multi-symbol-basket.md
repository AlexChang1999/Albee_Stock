# 交接：多標的籃子驗證（跨產業 OOS 池化）+ 全庫重驗

> **這份是給「下一個 session」的完整實作提示詞。** 直接照做即可，不用重新研究。
> 計劃已經使用者批准（含池化權重拍板）。背景見 `CHANGELOG.md`「未發布 → 待辦／規劃中」。

---

## 一句話目標

把候選策略驗證從「單一標的 SPY」升級成「**跨產業一籃子標的**」：每檔各跑 `walk_forward`，
把所有檔所有 fold 的 OOS EV **池化**後餵**同一支** `is_layer_worth_it`（judge / `is_noop`
**零修改**，只改餵料）。樣本從「1 檔 × 9 fold」變「N 檔 × 9 fold」，過擬合單檔風險大降。
然後**連 candidate 全庫重驗**，過不了的（含已晉升 7 筆 curated）降級。

> **關鍵洞察**：`is_layer_worth_it`（`backend/services/validation.py:146`）只吃一個 EV 數字
> 清單、不在乎來源 → 升級不用重寫判準，只要把多檔 fold 匯成一池。

---

## 起點狀態（接手前先 `git status` 確認）

- 前一任務「修 no-op 漏洞」**已完成並 commit**（`is_noop` 守門 + `rejudge_noop.py` 退 5 筆 +
  7 筆 validated 已被使用者人工晉升 curated）。
- 多標的本任務**程式幾乎是零**——之前以為 `config.py` 改過是幻覺，實際從沒落地。**全部重做**。
- venv 只在主 repo 根：`../../../venv/Scripts/python.exe`（worktree 裡用相對路徑）。
- `.env` 已複製進 worktree（gitignored，安全），指向 Neon，可連雲端 DB。

---

## 池化權重（使用者拍板，務必照做）

**不是**把所有 fold 無腦攤平（`pooled = 所有檔所有 fold`）——那會被交易次數多的標的吃走結果。
改採「**每檔等權 + 最低交易次數門檻**」：

1. 某檔在所有 fold 的**總 `num_round_trips` 未達門檻 X** → **整檔排除**（避免靠運氣少數幾筆大賺污染）。
   - 門檻 X 建議用 config 設定（如 `AUTO_VALIDATE_MIN_TRADES_PER_SYMBOL`，預設先抓個保守值如 5 或 10，
     並在 CHANGELOG 記錄選值理由）。
2. 達標的檔，**各自先算自己的平均 OOS EV**，再 **N 檔等權平均**成最終池化 EV。
   - 二擇一（實作時挑一個並在 CHANGELOG 記錄選法）：
     - (a) 每檔 = 該檔所有 fold 的 EV 平均；最終 = 各檔平均的等權平均。
     - (b) 每檔先算「每日平均 EV」（除以交易天數）再跨檔等權平均——兼顧高周轉短線特性。
   - **建議先做 (a)**（簡單、夠用），(b) 列為 future。
3. **judge 仍零改**：把「N 檔等權平均後的 EV 序列」當成餵給 `is_layer_worth_it` 的
   `candidate_oos`。最直觀做法：`candidate_oos = [每檔的平均EV for 每個達標檔]`、
   `baseline_oos = [0.0]*N`。這樣 fold 數檢查（`VALIDATION_MIN_FOLDS`）的語意要重新想清楚——
   原本一檔要 ≥3 fold，現在是「≥3 個達標的標的」還是「總 fold 數」？
   **拍板**：改成「達標標的數 ≥ 某下限」（如 ≥3 檔），避免單檔撐全場；在 CHANGELOG 寫明語意改動。

---

## 變更清單（一次一步、改完就測）

### 1. `backend/config.py` — 新增籃子設定（向後相容）

- 加 `AUTO_VALIDATE_SYMBOLS`（逗號字串），預設 `"SPY,AAPL,JPM,XOM,JNJ,CAT,WMT,NVDA"`。
- 加 `AUTO_VALIDATE_MIN_TRADES_PER_SYMBOL`（int，門檻 X）。
- 加 `@property auto_validate_symbols` → 拆逗號、去空白、轉大寫；空字串退回 `[AUTO_VALIDATE_SYMBOL]`
  （單檔相容、不破壞既有行為）。
- **保留** `AUTO_VALIDATE_SYMBOL` 不刪。
- `.env.example` 同步補這兩個新欄位 + 註解。

### 2. `backend/services/evolution.py` — 池化多檔（核心）

`validate_candidate` 由「吃單 symbol」升級成「吃 symbols（單檔或籃子皆可）」：

- 簽名改 `validate_candidate(knowledge_row, symbols, days=..., ...)`，內部把 `str` 正規化成
  `list[str]`（單檔呼叫端不破壞）。
- 對籃子**每檔**：`market_data.get_bars` → `validation.walk_forward` → 收集該檔 folds。
  - 某檔抓不到資料 / 太短湊不出 fold → **跳過該檔並記在 per_symbol 摘要**（不 raise 整批炸）；
    **全部檔都失敗才 raise**。
- **依拍板池化**（見上節）：每檔總 `num_round_trips` < 門檻 → 整檔排除；達標檔各算平均 EV → N 檔等權。
  - no-op 判定：跨檔達標檔數為 0（或全零交易）→ rejected 掛 `noop` 鍵（沿用 `is_noop` 純函式精神，
    但注意現在是「逐檔門檻」不是「單一 fold 清單全零」——可能要新增一個 helper 或調整 `is_noop`
    呼叫方式，**但判準精神不變**：沒真出手就不算加分）。
  - `verdict = is_layer_worth_it(baseline_oos, candidate_oos)`（**judge 零改**）。
- `oos_metrics` 擴充：新增 `"symbols"`（驗證籃子）、`"per_symbol"`（每檔 fold 數 / 總交易數 /
  平均 EV / 是否達標 / 是否被排除），看跨檔分布、抓「只靠某一檔撐」的假象；`expected_value`
  頭條＝池化平均；保留 `walk_forward` / `single_split` / `noop`/`verdict` 鍵的稽核區分不變。

### 3. `backend/services/auto_validate.py` — 改丟籃子

- `run_auto_validate` 把 `settings.AUTO_VALIDATE_SYMBOL`（`auto_validate.py:93`）換成
  `settings.auto_validate_symbols` 傳給 `validate_candidate`。其餘失敗隔離 / 批次 / 冪等不動。
- 檔頭註解第 13 行「驗證標的統一用 AUTO_VALIDATE_SYMBOL」要改成「統一用籃子」。

### 4. `backend/routers/knowledge.py` — 手動端點可選籃子

- `ValidateIn`（`knowledge.py:63/69`）的 `symbol: str = "AAPL"` 增補：允許 `symbols: list[str] | None`
  （不傳則用單 `symbol`，向後相容）。`validate_knowledge`（`:271`）轉呼新簽名。
- `promote_knowledge`（`:335`，人在迴路 validated→curated）**不要動**。

### 5. `scripts/revalidate_basket.py`（新）— 全庫重驗一次性維運

對 Neon 既有 knowledge 列**用新籃子重跑回測**（這次必須重跑，因為換了標的）：

- 取 `status in (candidate, validated, curated)` 逐筆 `validate_candidate(row, symbols=籃子)`。
- 結果自然流轉：candidate/validated → validated/rejected 照 verdict；**curated 過不了 → 降級**。
- ★ **curated 降級要慎重**：curated 是人晉升的。腳本**預設 dry-run** 印報告（每筆：舊→新 status、
  池化 EV、per_symbol 分布、哪幾檔被門檻排除 / 零交易）；`--apply` 才寫 DB；降級 curated 前印明顯警告行。
- 失敗隔離比照 `auto_validate.record_validation_failure`（單筆炸不擋整批）。
- ★ **JSON 欄位陷阱**：`Column(JSON)` 沒掛 MutableDict，就地 mutate 不持久化——整顆重建
  `oos_metrics` 再賦值（沿用 `rejudge_noop.py` / `record_validation_failure` 範式）。
- 吃 CPU：N 檔 × 回測 × 全庫筆數；逐筆 commit 防中途斷。

### 6. `tests/test_evolution.py` — 擴充籃子測試（不連網，monkeypatch）

`market_data.get_bars` 依 symbol 回不同合成 df、`validation.walk_forward` 回可控 fold：

- 籃子池化：2 檔各回正 EV fold → validated；`oos_metrics["per_symbol"]` 有兩檔。
- 跨檔 no-op：兩檔都零交易 → rejected 含 noop 鍵。
- 門檻排除：一檔交易數低於門檻 → 該檔被排除、用剩餘達標檔判。
- 單檔相容：傳 `str`（非 list）仍走原路徑、**既有 no-op 測試不破**。
- 某檔抓不到資料 → 跳過該檔、用剩餘檔判（不 raise）；全失敗才 raise。

### 7. `CHANGELOG.md`（未發布 → 修正）

實作完成後，把「待辦／規劃中」那條改寫成「修正／變更」已完成條目，記：單檔→籃子升級、
judge/`is_noop` 零改只是改餵料、新 config 兩欄、池化選法（每檔等權 + 門檻 X = ?）、fold 數語意
改動、全庫重驗結果（含 7 筆 curated 重驗後去留）、per_symbol 稽核欄。

---

## 驗證方式

```powershell
# 1) 單元測試（不連網）
..\..\..\venv\Scripts\python.exe -m pytest tests\test_evolution.py tests\test_auto_validate.py tests\test_validation.py -q

# 2) 全庫重驗：先 dry-run 看報告（每筆 舊→新 status + per_symbol 分布），確認合理再 --apply
..\..\..\venv\Scripts\python.exe scripts\revalidate_basket.py
..\..\..\venv\Scripts\python.exe scripts\revalidate_basket.py --apply

# 3) 確認雲端：GET /knowledge/ranking?status=validated → 看跨檔池化後留存清單
#    抽一筆看 oos_metrics.per_symbol → 各產業 fold 數 / 交易數 / EV 分布 / 是否被門檻排除
```

---

## 鐵則（別破壞）

- **judge 零改**：`is_layer_worth_it` / `VALIDATION_MIN_IMPROVEMENT=0` 都不動，只改餵進去的料。
- **回測=實盤**：資料一律 `market_data.get_bars(..., source=settings.DATA_SOURCE)`，別寫死。
- **人在迴路**：validated→curated 只能人按；腳本 / 排程**不准**自動晉升 curated。
- **預設全關**：`DISCOVERY_ENABLED` / `AUTO_VALIDATE_ENABLED` 保持 false。
- **一次一步**：每改一個檔就跑對應測試，別一次動太多。
- DB 不靠手動 ALTER（這任務不動 schema；失敗計數塞 `oos_metrics` JSON，免遷移）。

## 關鍵檔案行號（接手時可能位移，以 grep 為準）

- `backend/services/evolution.py:41`（validate_candidate）、`:27`（is_noop）
- `backend/services/validation.py:60`（walk_forward）、`:146`（is_layer_worth_it — **不動**）
- `backend/services/auto_validate.py:93`（改丟籃子）
- `backend/routers/knowledge.py:63/69/271`（ValidateIn / validate）、`:335`（promote — **不動**）
- `backend/config.py`（新增 AUTO_VALIDATE_SYMBOLS + MIN_TRADES + property）
- 新建：`scripts/revalidate_basket.py`；擴充：`tests/test_evolution.py`、`.env.example`、`CHANGELOG.md`
