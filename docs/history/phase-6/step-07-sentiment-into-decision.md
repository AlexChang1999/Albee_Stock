# 步驟 7 — AI 情緒真正進決策

> 修 **P5**（死掉的 AI 情緒層）。使用者明確要求。回到 [Phase 6 索引](README.md)。

## 目標

讓第二層 LLM 算出的情緒分數**真正影響部署決策**，而非算完就丟。讓「AI 驅動」名副其實，
同時守住「EV 為主、情緒為輔」的紀律——情緒只能否決或微調，不能蓋過期望值。

## 問題（現況）

`screener.screen_watchlist` 的漏斗第二層對 survivors 跑本機 Ollama 算 `sentiment`（label / score / reason），
把它掛進每筆推薦。但：
- `screen_watchlist` 最終**排序只看 EV**。
- `automation.plan_deployments` **只讀 `expected_value` / `win_rate_pct`，完全忽略 `sentiment`**。

結果：第二層 LLM 燒了算力、做了情緒分析，卻不影響任何決策——典型的 vibe slop（算了沒人用）。

## 改動

1. **`backend/config.py`** 新增：
   - `SENTIMENT_GATING`（預設 `true`，總開關）。
   - `SENTIMENT_MIN_SCORE`（預設例如 `-20`，低於此視為「情緒否決」）。
2. 新增純函式 **`apply_sentiment(recommendations, *, min_score, enabled) -> list`**：
   - 規則（明確、可測）：`sentiment.label == "bearish"` 或 `score < min_score` → **否決部署**（從 deploy 候選剔除；保留 `vetoed_by_sentiment=True` 旗標讓 UI 仍能顯示「情緒否決」）。
   - 非否決者：以 `score` 作為 **OOS EV 排序的次要加權**（EV 為主排序鍵、情緒為次，避免情緒蓋過期望值）。
   - `sentiment is None`（LLM 沒跑 / 被外送閘擋下）→ 視為中性、**不否決**（維持 best-effort、離線不阻斷）。
   - `enabled=False` → 原樣回傳（退回純 EV 行為）。
3. **`backend/services/automation.py`** 的 `plan_deployments`：在 EV / 勝率門檻**之後**串接 `apply_sentiment`。
4. **`backend/services/screener.py`** 的 `screen_watchlist`：最終排序鍵改 `(OOS EV, sentiment_score)`。

## 重用既有

- `screener.parse_sentiment` 已產出一致格式的 `{label, score, reason}`（含 None 情境）。
- `plan_deployments` 既有的純函式測試慣例。

## 測試

- monkeypatch 出 `bearish` / `neutral` / `None` / `score 低於門檻` 四種情緒，驗證否決與加權行為。
- 驗證 `SENTIMENT_GATING=false` 時完全退回純 EV 排序（向後相容）。
- 驗證情緒**不會**把一個 OOS EV 更高的標的排到更低 EV 標的後面（EV 仍為主）。

## 驗收

- monkeypatch bearish 情緒，確認該標的被「情緒否決」、不進 deploy，但 UI 仍看得到它與否決原因。
- 兩檔 EV 相近時，情緒較正的排前面；EV 差距大時，情緒不翻盤。
