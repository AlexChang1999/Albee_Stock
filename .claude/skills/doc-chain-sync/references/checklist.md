# 漂移熱點與掃描清單（開掃前先讀）

> 歷次健檢證實最容易爛的地方。每次健檢先掃這張表，再走全鏈。
> 本表本身也是文件——健檢發現新熱點就補進來（含日期）。

## 高風險漂移熱點（每次必查）

| 熱點 | 核實方法 | 曾炸紀錄 |
|------|----------|----------|
| `CLAUDE.md` 開發階段表 vs `docs/history/phase-*/` 實夾 | Glob history 夾、逐 README 讀進度表 | 2026-06-11（停在 6–7）、2026-07-04（缺 14/15/16） |
| `CLAUDE.md` 專案結構樹 vs `backend/{services,strategies}/*.py`、`frontend/src/pages/*.jsx` | Glob 實檔對照樹 | 同上兩次 |
| `docs/README.md` 索引表 vs `docs/**` 實檔 | Glob docs 全 md，逐列對索引 | 2026-07-04（漏 analysis-2026-07-03） |
| backlog 項數/剩餘建議（`remaining-work-backlog.md` 頭部 + 被引用處） | 讀盤點總表數列 | 2026-07-04（A~G 實為 A~H、剩餘清單過期） |
| 各處「數字型」描述：策略 N 種 / 前端 N 頁 / 工作流圖 N 張 / 測試 N 個 | grep `STRATEGY_REGISTRY`、glob pages、grep `^## 圖` | 2026-07-04（9→12 策略、17→20 頁、4→6 圖） |
| root `README.md` 技術棧/進度表（最少人維護、最常給外人看） | 對照 CLAUDE.md 與實況 | 2026-07-04（DB 還寫 SQLite、進度停 Phase 10） |
| skill `references/` vs SKILL.md（同一次修訂常漏掃 reference 檔） | 逐 skill 讀主檔+references 對數字/步驟 | 2026-07-04（how-to-register「兩處」vs「四處」） |
| `explorations/INDEX.md` vs 實檔 | Glob explorations/*.md 對索引行 | 2026-07-04（review-2026-07-02 漏路標） |
| Phase README 進度表 vs 上層（docs/README、CLAUDE.md）轉述 | 讀 Phase README 進度表 | 2026-07-04（docs/README 說 M1~M3，實為 M1~M10+M12） |

## 同套規則的多份副本（改一處必同步他處）

- 策略「6 個落地點」表：`backend/strategies/CLAUDE.md` ⇄ `.claude/skills/strategy-builder/references/how-to-register.md`
- 「回測=實盤」鐵則：`CLAUDE.md` 已知注意事項 ⇄ `docs/ai-implementation-guardrails.md` 第壹/伍節 ⇄ backlog 通用鐵則
- 雙閘（+第三閘 leader lock）說法：`CLAUDE.md` 重要規則 ⇄ root `README.md` 注意事項 ⇄ guardrails 鐵則 1
- backlog 描述行：`CLAUDE.md` docs 樹註解 ⇄ `docs/README.md` 索引列

## 驗證用關鍵字掃法

修完把「被修掉的舊說法」原字串掃一遍，殘留須為 0：

```
範圍：CLAUDE.md, README.md, docs/**/*.md, .claude/skills/**/*.md, explorations/INDEX.md
排除：venv/, frontend/node_modules/, docs 內標明「原始步驟留作歷史」「✅ 已完成」的史料段
```

歷史段判法：該段落開頭有「已完成」「留作歷史紀錄」字樣 → 殘留屬史料，不修不計。

## Windows 坑（掃描/寫檔時）

- 中文檔名存在（`docs/guides/使用說明.md`），glob/grep 走工具內建，別用 cmd dir。
- 寫報告檔一律 UTF-8（PowerShell 5.1 預設 UTF-16 BOM 會讓 grep 讀爛）。
