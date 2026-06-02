# Anthropic `financial-services` 摘錄 — 對本專案有用的部分

> **來源**：[anthropics/financial-services](https://github.com/anthropics/financial-services)
> （本機完整副本：`D:\reference\financial-services`，僅供參考閱讀，不納入本專案 git）
> **摘錄日期**：2026-06-02

---

## 一、這個 repo 是什麼（先講清楚定位）

Anthropic 官方的 **Claude 金融分析 skills / agents 範本庫**。
做的是「**產出分析報告草稿、給人類審核**」——例如財報分析、估值模型、選股研究。

⚠️ **它明確聲明不執行交易、不下單、不碰真實風險**。
所以它**不是**自動交易引擎，跟我們 `backend/` 的 Alpaca 下單邏輯方向不同。

**結論**：不要整包塞進交易系統。它的價值在「**怎麼寫好 Skill**」和「**選股/基本面過濾的思路**」這兩塊。

---

## 二、最有用的三個借鏡

### 1. Skill 的標準寫法（漸進式揭露）⭐ 最值得學

它的每個 skill 都長這樣，跟我們 `docs/skill-guidelines.md` 講的原則一致，可當實際範例：

```
skills/earnings-analysis/
├── SKILL.md              # 主檔：frontmatter (name + description) + 核心指引
├── references/           # 進階細節，需要時才載入（省 token）
│   ├── best-practices.md
│   ├── report-structure.md
│   └── workflow.md
└── assets/               # 範本/檢查清單
    └── quality-checklist.md
```

`SKILL.md` 的 frontmatter 範例（`description` 寫清楚「何時觸發」是關鍵）：

```markdown
---
name: idea-generation
description: Systematic stock screening... Triggers on "stock screen",
  "find ideas", "screen for", "new ideas".
---
```

**對我們的應用**：之後要寫自己的 skill（放 `.claude/skills/`）時，照這個資料夾結構：
主檔精簡、細節丟 `references/`、範本丟 `assets/`。`description` 要寫觸發詞。

### 2. Slash command 接 skill 的寫法

`commands/morning-note.md` 只有幾行，作用是「載入某 skill 並下指令」：

```markdown
---
description: Draft a morning meeting note
argument-hint: ""
---
Load the `morning-note` skill and draft a concise morning note...
```

**對我們的應用**：未來想做 `/盤前掃描`、`/bot健檢` 之類的快捷指令，就是這個模式——
一個薄薄的 command 檔，負責叫對應 skill 做事。

### 3. 選股篩選條件（`idea-generation` skill）⭐ 可餵進策略設計

它列了一套量化選股條件，**可以轉成我們新策略的進場過濾器**。摘錄：

| 風格 | 條件（可換算成程式判斷） |
|------|------|
| **價值 Value** | P/E < 同業中位數、EV/EBITDA < 歷史均值、FCF yield > 5%、P/B < 1.5x |
| **成長 Growth** | 營收 YoY > 15%、EPS YoY > 20%、營收成長率加速、毛利擴張、ROIC > 15% |
| **品質 Quality** | 連續 5 年營收成長、ROE > 15%、低負債比、高自由現金流轉換 |
| **放空 Short** | 營收衰退、毛利壓縮、應收/存貨成長快於營收、內部人賣股、會計紅旗 |

**對我們的應用**：目前我們策略都是**純技術指標**（MA/RSI/MACD…）。
這份清單是**基本面**角度，可當未來「基本面過濾層」的設計藍圖——
例如 Bot 出技術訊號後，再用「營收成長 + 低負債」這類條件做二次確認，過濾雜訊。

---

## 三、未來可考慮的方向（非現在）

Phase 4 把自動交易跑穩之後，若要加「AI 輔助層」，這 repo 的
`equity-research` / `market-researcher` 是現成參考：

- **技術訊號 + 基本面確認**：Bot 觸發買訊 → 叫 Claude 讀最新財報/新聞 →
  回一句「基本面有無紅旗」當**額外過濾**（不是下單依據，只是多一道保險）。
- **盤前 morning note**：每天自動產一份「持倉相關隔夜消息 + 風險提醒」。

⚠️ 這些是**加分功能、非核心**。新手階段先把現有自動交易做穩，別分心。

---

## 四、它的「來源引用紀律」也值得抄

`earnings-analysis` 強制要求每個數字都標**具體出處 + 可點連結**（10-Q、財報發布頁）。
我們未來若做 AI 產出的分析報告，同樣該要求「每個結論標資料來源」，避免幻覺亂編數字。

---

## 五、不用碰的部分

以下對我們專案無關，略過：
- `model-builder`（Excel DCF/LBO 模型）
- `gl-reconciler` / `month-end-closer`（會計對帳）
- `kyc-screener`（開戶盡職調查）
- `pitch-agent`（投行簡報）
- 各家付費資料商 MCP 連接器（FactSet/S&P/Morningstar… 我們用 Alpaca）
