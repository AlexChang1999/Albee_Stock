---
name: doc-chain-sync
description: 對本專案的「系統文件鏈」（CLAUDE.md → README → docs/README 索引 → guardrails/backlog → guides/reference/ux → .claude/skills → explorations/INDEX）做一次全鏈健檢與同步：抓缺漏/衝突/過期/斷鏈四類問題，缺漏直接修、衝突停下出裁定題，修完用舊關鍵字掃殘留並出固定格式報告。當使用者說「全鏈同步」「文件健檢」「系統健檢」「文件同步」「掃文件漂移」「doc sync」時觸發。對象是規範/SOP/索引/skill 本身，不是產出內容；改程式碼行為不歸本 skill 管。
---

# 文件全鏈同步健檢（doc-chain-sync）

把「規範文件、索引、SOP、skill」當成一條鏈做健檢：上層定的規則，下層要接得住；
同一規則全系統只准存在一套說法。**對象是系統本身，非產出內容。**

## 何時觸發 / 何時不觸發

- **觸發**：使用者喊「全鏈同步」「文件健檢」等；或大改動（新 Phase 落地、砍模組、
  換基礎設施）收工後使用者要求同步。
- **不觸發**：單點小修（改哪份就順手同步相關文件即可，不必全鏈掃）；
  改程式行為（那是 feature/bugfix，走 guardrails 合約）；產出內容（回測報告、探討檔）的對錯。
- **退場**：報告發出即結束。衝突項等使用者裁定，裁定後只補修該項＋驗證，不重掃全鏈。

## 讀檔順序（逐鏈，禁跳讀）

1. `CLAUDE.md`（主規範）→ 2. `README.md`（對外門面）→ 3. `docs/README.md`（文件地圖索引）
→ 4. `docs/ai-implementation-guardrails.md` + `docs/remaining-work-backlog.md`（上層策略）
→ 5. `docs/{guides,reference,ux}/`（各 SOP；對照索引表逐列）→ 6. `docs/history/phase-*/README.md`
（各 Phase 進度表 vs 上層階段表）→ 7. `.claude/skills/*/SKILL.md` + `references/`
→ 8. `explorations/INDEX.md` vs 實檔清單。

每份文件對照上下層抓四類問題：

| 類 | 定義 | 處置 |
|----|------|------|
| A 缺漏 | 上層定了規則/實檔存在，下層沒接住/索引沒路標 | 直接修 |
| B 衝突 | 兩份文件（或同檔兩處）講不同標準，且修法有兩種以上合理選擇 | **停，出裁定題給使用者**（附選項+建議），裁定前不動手 |
| C 過期 | 已定案新規則，舊說法殘留（含數字停在舊版） | 直接修 |
| D 斷鏈 | 引用的檔名/路徑/數字對不上實檔 | 直接修 |

**安全閥：禁止把衝突當缺漏擅自修。** 判準：修法只有一種答案才算缺漏/過期。
若新版有 CHANGELOG/commit 佐證定案，舊說法判過期非衝突，可直修。

## 鐵律（避坑）

- **每個問題必須實際開檔核對才算數**，禁憑目錄、印象、上次健檢結果回報。回報附「哪個檔、哪一段」。
- **數字必核實**：頁數 glob `frontend/src/pages/*.jsx`、策略數 grep `STRATEGY_REGISTRY`、
  測試數 glob `tests/test_*.py`、圖張數 grep `^## 圖`——別信文件自己寫的數。
- 常見漂移熱點與關鍵字掃描清單見 [`references/checklist.md`](references/checklist.md)（開掃前先讀）。
- 小幅優化**禁翻主軸**；歷史紀錄段（「原始步驟留作歷史」「✅ 已完成」節）是史料，殘留舊說法**不修**。
- 搬移既有檔一律 `git mv`；連結用相對路徑並確認解析得到。
- 備份**只在使用者說「做備份」時做**（原檔名_backup_日期 → 備份夾，逐檔比對）；
  修改前禁主動備份、禁問要不要備份。

## 修完必做（記憶落地，跨對話）

1. **驗證**：用「被修掉的舊說法」當關鍵字掃全系統（範圍：`CLAUDE.md`、`README.md`、
   `docs/**`、`.claude/skills/**`、`explorations/INDEX.md`，排除 venv/node_modules），殘留須為 0。
   報告中引用的檔名/路徑逐一 Glob 確認實檔在。
2. **CHANGELOG.md** 未發布區塊記一條（改了哪些檔、修了什麼類）。
3. **紀錄檔落地**：`explorations/doc-sync-<YYYY-MM-DD>.md` 存本次報告全文 +
   `explorations/INDEX.md` 加一行路標（下次健檢先讀上次紀錄，只掃增量熱點）。
4. **報告固定格式**：缺漏 N 項（已修）／衝突 N 項（待裁定或已裁定）／過期斷鏈 N 項（已修）／
   skill 化建議／驗證結果／動過的檔案完整列表。
