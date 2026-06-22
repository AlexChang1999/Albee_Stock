# Phase 12 — 端到端驗收紀錄（step-05）

> **文件狀態：模板（觀察期未開跑）。** step-01~04 程式已落地（2026-06-11），但兩週觀察
> 需在常駐運行的機器上全開連跑——開跑時填「觀察設定」，跑滿兩週回填數據與結論。
> 原契約：[step-05-e2e-honest-review.md](step-05-e2e-honest-review.md)。
>
> **判準凍結聲明**：評估期內**不准**調鬆任何 OOS 門檻（`evolution` / `validation` 的
> 通過判準、`_MIN_CONFIDENCE` 信心下限）。改了判準 = 本次觀察作廢重來。

---

## 一、觀察設定（開跑時填）

| 項目 | 值 |
|------|-----|
| 觀察起日 | ____-__-__ |
| 觀察迄日（起日 +14 天） | ____-__-__ |
| `COLLECTOR_RSS_FEEDS` | （列出 feed 清單） |
| `COLLECTOR_INTERVAL_MIN` | （建議 60） |
| `DISCOVERY_ENABLED` | true |
| `AUTO_VALIDATE_ENABLED` | true |
| `AUTO_VALIDATE_SYMBOL` | （預設 SPY） |
| 期間人工干預 | 無（鐵則：晉升 curated 以外不准手動推狀態） |

起跑當下快照 `GET /company/overview` 的 `discovery_funnel` 區塊，貼這裡：

```json
（起日快照）
```

---

## 二、漏斗數據（跑滿兩週回填；迄日再快照一次 discovery_funnel，算兩次差值）

```json
（迄日快照）
```

| 指標 | 算法 | 值 |
|------|------|-----|
| raw 收料量 | 迄日 raw 四狀態合計 − 起日合計 | |
| 垃圾率 | discarded 增量 ÷ raw 收料量 | |
| candidate 產量 | 探勘橋 built 增量 | |
| OOS 通過率 | validated 增量 ÷ (validated 增量 + verdict-rejected 增量)※ | |
| 人工晉升量（curated 增量） | 迄日 curated − 起日 curated | |

> ※ **分母排除 `rejected_by=auto_validate` 的列**（`oos_metrics` 只有 `auto_validate` 鍵、
> 沒有 `verdict` 鍵的 rejected = 操作性放棄，例如資料源連炸 3 天，不是策略不好，
> 不准灌進「策略淘汰率」污染通過率）。
> 淘汰率高是健康的：大部分網路點子過不了 OOS 閘是預期結果，不是 bug。

---

## 三、基準對照

| 基準 | 算法 | 值 |
|------|------|-----|
| optimizer 網格掃描 OOS 通過率 | 同期跑一次全自動掃描，過 `AUTO_DEPLOY_EV_THRESHOLD` 門檻的組合數 ÷ 總組合數 | |

---

## 四、結論（三選一，照 step-05 契約判準勾選）

- [ ] **留**：LLM 提案通過率 ≥ 網格基準、且 curated 有增量 → 管線常開。
- [ ] **降級**：通過率低但素材有閱讀價值 → 排程關閉（`DISCOVERY_ENABLED` /
      `AUTO_VALIDATE_ENABLED` 設回 false）、collector 留著當人工靈感收件匣（回 Phase 10 狀態）。
- [ ] **砍**：素材垃圾率高 + 零通過 → 關 feeds，記錄教訓。
- [ ] **延長觀察**：兩週數據不夠下定論 → 寫延長理由 + **新截止日 ____-__-__**（不准無限期掛著）。

結論理由（數據說話）：

> （回填）

---

## 五、收尾動作（結論定了之後）

1. 更新本檔狀態：模板 → 已完成。
2. [`README.md`](README.md) 文件狀態同步（已完成 / 已降級）。
3. [`../../remaining-work-backlog.md`](../../remaining-work-backlog.md) D 項標結論。
4. `CHANGELOG.md` 記結論。
5. 若降級 / 砍：flags 全關後跑 `venv\Scripts\python.exe -m pytest tests\ -q` 全綠
   （回歸驗收：行為 = 開工前）。
