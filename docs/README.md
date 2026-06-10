# 文件地圖（docs/ 索引）

> 打開 `docs/` 先看這頁。文件按**用途**分四夾，完成過的開發藍圖收進 `history/`，
> 根目錄只留「最常讀」兩份。任何檔都沒刪，純搬移分類。

## 最常讀（留在 docs/ 根）

| 檔案 | 用途 |
|------|------|
| [`ai-implementation-guardrails.md`](ai-implementation-guardrails.md) | **開工前必讀**：AI／人拿藍圖自己 coding 的防偏離合約（反 slop、對齊原目標、DoD）。 |
| [`remaining-work-backlog.md`](remaining-work-backlog.md) | 進行中的未完成工作盤點（A~G 七項，含詳細 step，可餵 AI 實作）。 |

## history/ — 開發歷史藍圖（做歷史歷程報告的主素材）

各 Phase 開工前的契約文件（原目標 / step / DoD / 誠實邊界）。已落地、收進此夾備查。

| 夾 | 內容 |
|----|------|
| [`history/phase-6/`](history/phase-6/README.md) | 可信度地基（成本/隔日成交/OOS/統一資料路徑/組合風控/決策審計，step-01~10）。 |
| [`history/phase-7-adaptive-regime/`](history/phase-7-adaptive-regime/README.md) | 自適應市場狀態（狀態辨識→選策略 + 凱利 + meta-labeling + 防過擬合，step-01~07）。 |
| [`history/phase-8-strategy-evolution/`](history/phase-8-strategy-evolution/README.md) | 策略知識庫 + 組合進化（step-01~06）。 |
| [`history/phase-9-frontend-workstation/`](history/phase-9-frontend-workstation/README.md) | 專業前端工作站（sidebar + 多頁，step-01~08）。 |
| [`history/phase-10-ai-company/`](history/phase-10-ai-company/README.md) | AI 交易公司（戰情頁/蒐集員/政治員/董事會核准/常駐化，step-01~07）。 |
| [`history/phase-11-macro-data/`](history/phase-11-macro-data/README.md) | 總經環境資料地基（FRED/快取/環境特徵/引擎吃 features/OOS 驗證，step-01~05）。 |
| [`history/redesign/`](history/redesign/README.md) | 「AI 終端機改版」子軌（圖表/AI 推薦/深藍主題/自動化，P1~P4）。 |

## guides/ — 操作與教學

| 檔案 | 用途 |
|------|------|
| [`guides/setup.md`](guides/setup.md) | 環境設置（換新電腦一鍵建好開發環境）。 |
| [`guides/使用說明.md`](guides/使用說明.md) | 日常操作流程（啟動、前端各分頁、檔案位置、安全雙閘、FAQ）。 |
| [`guides/how-to-add-strategy.md`](guides/how-to-add-strategy.md) | 新增策略 runbook。 |
| [`guides/setup-postgres-sync.md`](guides/setup-postgres-sync.md) | 換 PostgreSQL／同步設定。 |
| [`guides/phase4-paper-checklist.md`](guides/phase4-paper-checklist.md) | Paper Trading 上線前檢查表。 |
| [`guides/skill-guidelines.md`](guides/skill-guidelines.md) | 撰寫 Skill 的守則。 |

## reference/ — 概念／規格／路線

| 檔案 | 用途 |
|------|------|
| [`reference/workflow-diagrams.md`](reference/workflow-diagrams.md) | 系統工作流圖（Mermaid：全景/決策流水線/回測 EV/層驗證）。 |
| [`reference/roadmap-strategy-workbench.md`](reference/roadmap-strategy-workbench.md) | 策略工作台 roadmap（Phase 5）。 |
| [`reference/human-vs-ai-operation.md`](reference/human-vs-ai-operation.md) | 人機操作落差 + 分階段上線（跑真錢前必讀）。 |
| [`reference/financial-services-reference.md`](reference/financial-services-reference.md) | 金融服務參考。 |
| [`reference/strategies/`](reference/strategies/) | 個別策略筆記（如 `williams_r.md`）。 |

## ux/ — 前端 UX

| 檔案 | 用途 |
|------|------|
| [`ux/ux-workflow.md`](ux/ux-workflow.md) | UX 工作流（何時觸發 skill + 優先序閘門 + 交付前檢查表）。 |
| [`ux/ux-audit-2026-06.md`](ux/ux-audit-2026-06.md) | 前端 UX 稽核報告。 |
