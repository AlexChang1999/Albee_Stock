# Phase 8 — 策略知識庫 + 組合進化（人在迴路）

> **文件狀態：構想 / 研究階段。** 把「蒐集很多策略 → 整合組合 → 驗證 → 留存 → 再進化」串成人在迴路的閉環。
> **開工前必讀 [`../ai-implementation-guardrails.md`](../ai-implementation-guardrails.md)（防漂移 + 防 slop 合約）。**
> **強依賴 Phase 6（誠實 OOS）與 Phase 7 step-07（防過擬合）——前置沒做完不要開始本 Phase。**
>
> 撰寫日期：2026-06-05。

---

## 〇、使用者願景（原話釐清）

> 「策略資料庫（依不同理論、場景有不同策略說明 / 場景），Albee Stock 能據此生成不同交易策略並驗證，
> 給使用時機說明，讓程式可成長、自行進化。像是蒐集很多策略後進行整合、結合。然後形成不同 Bot，回測、推演。」

使用者澄清：**不是「只從凱利延伸」，而是「蒐集很多策略 → 整合組合 → 人在迴路審核」**。

---

## 壹、可行性結論（誠實）

**可行，且一半零件已存在：**

| 願景環節 | 已有的零件 | 路徑 |
|----------|-----------|------|
| 生成策略 | `strategy-builder` skill（人講的策略→可跑模組） | `.claude/skills/strategy-builder/` |
| 參數搜尋 | `optimizer.PARAM_GRIDS` + `run_auto_backtest` | `backend/services/optimizer.py` |
| 驗證 | `backtest_engine._run_on_df` + Phase 6 OOS | `backend/services/backtest_engine.py` |
| 已驗證策略庫 / 記憶 | `strategy_presets` / `backtest_runs` / `explorations` | `backend/models/`、`backend/services/explorations.py` |

缺的只是把它們串成閉環 + 一個「組合引擎」。

> ⚠️ **瓶頸不在生成（很容易），在驗證它不是運氣。** 大量生成 = 大量多重測試，必然撈到假冠軍。
> **Phase 7 [step-07 防過擬合框架](../phase-7-adaptive-regime/step-07-anti-overfitting-validation.md) 是強制守門。**
> 小修正：**凱利是「部位大小」不是「進出場訊號」**，所以是「凱利部位法 × 任一訊號策略」的結合，非「從凱利長出策略」。

---

## 貳、目標架構（人在迴路閉環）

```
 策略知識庫（理論/場景/使用時機）
        │  ① 生成器（strategy-builder skill + LLM 提案）
        ▼
   候選策略區（未驗證，不上線）
        │  ② 組合引擎（多個已驗證子策略 → CompositeStrategy）
        ▼
   自動驗證管線（回測 → Phase6 OOS → Phase7 step-07 walk-forward/purged CV → 評分）
        │  ③ 只有「OOS 真加分」的才通過
        ▼
   人在迴路審核（使用者看排行榜 → 晉升 / 退回 / 送部署）
        │  ④ 採用/淘汰理由寫進 explorations 記憶
        ▼
   已策展策略庫（附 EV + 狀態親和性 + 使用時機說明）──► 一鍵轉 Bot（重用 createBot+startBot）
```

**人在迴路**：AI 只負責「提案 + 自動驗證 + 排序」，**晉升決定權在使用者**（呼應護欄「不確定就停」）。

---

## 參、施工路線（6 步）

| 步驟 | 文件 | 主題 | 依賴 |
|------|------|------|------|
| 1 | [step-01-knowledge-base-model.md](step-01-knowledge-base-model.md) | 策略知識庫資料模型 | Phase 6 |
| 2 | [step-02-strategy-generator.md](step-02-strategy-generator.md) | 策略生成器（skill + LLM 提案） | step-01 |
| 3 | [step-03-composite-engine.md](step-03-composite-engine.md) | 策略組合引擎（Ensemble，使用者強調的「整合」） | step-01 |
| 4 | [step-04-validation-pipeline.md](step-04-validation-pipeline.md) | 自動驗證管線（OOS + 防過擬合） | Phase 6+7、step-03 |
| 5 | [step-05-library-ranking.md](step-05-library-ranking.md) | 策略庫排行 + 使用時機說明 | step-04、Phase 7 |
| 6 | [step-06-human-review.md](step-06-human-review.md) | 人在迴路審核流程 | step-04/05 |

> 建議順序：1 → 3 → 4 →（4 綠了才接）2 → 5 → 6。先把「組合 + 驗證」這條最有價值的骨幹打通，再接 LLM 生成與審核 UI。

---

## 肆、明確界線（防 slop / 防漂移）

- **不做全自動進化**（使用者選人在迴路）：生成與驗證可自動，**晉升一律人工**。
- **每加一層（組合 / 生成 / 評分）都要先在 OOS 上證明加分**，加不了就砍（砍掉也記 CHANGELOG）。
- **不重造**回測 / EV / 資料抓取——用第參節既有零件。
- **不在 Phase 6/7 完成前動工**（地基的勝率為假，整個進化就是自我過擬合）。
- 全程 Paper + 雙閘安全閥不碰。
