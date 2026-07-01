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
| [`history/phase-12-strategy-discovery/`](history/phase-12-strategy-discovery/README.md) | 策略自動探勘入庫管線**藍圖**（收料→LLM 產候選→自動 OOS 閘→人在迴路晉升，step-01~05，未開工）。 |
| [`history/redesign/`](history/redesign/README.md) | 「AI 終端機改版」子軌（圖表/AI 推薦/深藍主題/自動化，P1~P4）。 |

## guides/ — 操作與教學

| 檔案 | 用途 |
|------|------|
| [`guides/setup.md`](guides/setup.md) | 環境設置（換新電腦一鍵建好開發環境）。 |
| [`guides/home-boot-checklist.md`](guides/home-boot-checklist.md) | 回家開機測試 checklist（`.env` 最小必填、雲端 PG 方案 A/B、step-01 驗收、缺口盤點）。 |
| [`guides/free-vm-deployment.md`](guides/free-vm-deployment.md) | 免費 VM 常駐部署（Oracle A1 開通、Linux 裝機、時區/systemd 坑、政治員 Discord bridge service、雲端 LLM 備援；Phase 12 觀察期用）。 |
| [`guides/cloud-local-division.md`](guides/cloud-local-division.md) | **雲端／地端工作劃分**：誰在哪跑、不可雙開排程的紅線、功能對照表、本機前端連雲端、Micro 健康監控。 |
| [`guides/cicd-vm-setup.md`](guides/cicd-vm-setup.md) | **CICD 上雲 runbook**：手動部署 / 補 GitHub Secrets（VM_HOST/USER/SSH_KEY）/ 免密碼 sudo / 關掃描走 DB 非 .env / Git Bash 連 VM / 驗單實例（2026-06 部署斷層修復）。 |
| [`guides/oci-grab-a1.md`](guides/oci-grab-a1.md) | 搶 A1.Flex runbook：第二台 Micro 掛 OCI CLI 重試腳本（`scripts/grab-a1.sh`）等容量釋出。 |
| [`guides/使用說明.md`](guides/使用說明.md) | 日常操作流程（啟動、前端各分頁、檔案位置、安全雙閘、FAQ）。 |
| [`guides/how-to-add-strategy.md`](guides/how-to-add-strategy.md) | 新增策略 runbook。 |
| [`guides/macro-layer-validation-runbook.md`](guides/macro-layer-validation-runbook.md) | Backlog A：拿到 FRED key 後跑 macro 層真資料 OOS 驗證 + 留/砍決策的步驟單。 |
| [`guides/deadman-switch-runbook.md`](guides/deadman-switch-runbook.md) | 維運安全軌 H2：healthchecks.io dead-man switch 設定、警報排查、每月演練。 |
| [`guides/collector-feeds-guide.md`](guides/collector-feeds-guide.md) | 市場蒐集員 feed 設定（推薦來源、robots 檢查、`.env` 範例、驗收 runbook，Phase 12 step-01）。 |
| [`guides/enable-auto-pipelines.md`](guides/enable-auto-pipelines.md) | **開啟自動管線** runbook：自動選標的（screener/opportunity）vs 策略點子探勘（collector→discovery→驗證）兩條線各開哪些開關、怎麼驗證；預設全關。 |
| [`guides/setup-postgres-sync.md`](guides/setup-postgres-sync.md) | **Neon 雲端 PostgreSQL** 設定／搬遷／**新電腦完整設置** runbook（2026-06-12 已正式切換）。 |
| [`guides/phase4-paper-checklist.md`](guides/phase4-paper-checklist.md) | Paper Trading 上線前檢查表。 |
| [`guides/smoke-test-plan.md`](guides/smoke-test-plan.md) | **煙霧測試計畫書**：上線前/部署後/換機後一鍵驗系統健康（L1 後端啟動+API／L2 前端 build／L3 部署健檢／L4 外部整合降級）；對應 `tests/test_smoke.py` + `scripts/smoke_test.sh` + CI frontend job。 |
| [`guides/skill-guidelines.md`](guides/skill-guidelines.md) | 撰寫 Skill 的守則。 |

## reference/ — 概念／規格／路線

| 檔案 | 用途 |
|------|------|
| [`reference/workflow-diagrams.md`](reference/workflow-diagrams.md) | 系統工作流圖（Mermaid 6 張：全景/決策流水線/回測 EV/層驗證/知識庫→AI 公司軌含 Phase 12 探勘管線/手工新增策略）。 |
| [`reference/frontend-pages-map.md`](reference/frontend-pages-map.md) | 前端 17 頁地圖（Mermaid 小圖×6）：四條工作流 + 開第一隻 Bot 步驟 + When/What/Why 對照 + 各頁資料由誰產生。 |
| [`reference/strategy-pipeline-workflow.md`](reference/strategy-pipeline-workflow.md) | **11 模組策略探勘工作流**（操作者視角）：蒐集員→AI探勘→進化實驗室→知識庫→自動化主水管 + 政治員煞車 + 5 條旁路；人只在「晉升 curated／跑真錢」出手 + 品質地基（參數 schema 漏洞修補）。 |
| [`reference/roadmap-strategy-workbench.md`](reference/roadmap-strategy-workbench.md) | 策略工作台 roadmap（Phase 5）。 |
| [`reference/human-vs-ai-operation.md`](reference/human-vs-ai-operation.md) | 人機操作落差 + 分階段上線（跑真錢前必讀）。 |
| [`reference/one-person-company-gap-analysis.md`](reference/one-person-company-gap-analysis.md) | 一人公司缺口盤點（願景 vs 現況 + 前置進料未通電 + 上線後維運缺口 + 優先序）。 |
| [`reference/financial-services-reference.md`](reference/financial-services-reference.md) | 金融服務參考。 |
| [`reference/rl-feasibility-assessment.md`](reference/rl-feasibility-assessment.md) | 強化學習（DQN/PPO）交易員可行性評估：現階段 No-Go + 重啟條件。 |
| [`reference/dev-pitfalls-log.md`](reference/dev-pitfalls-log.md) | 開發踩坑紀錄：歷來實際炸過、用 commit 修掉的坑（症狀/根因/修法/出處），CLAUDE.md 鐵則的完整史料版。 |
| [`reference/strategies/`](reference/strategies/) | 個別策略筆記（如 `williams_r.md`）。 |

## ux/ — 前端 UX

| 檔案 | 用途 |
|------|------|
| [`ux/ux-workflow.md`](ux/ux-workflow.md) | UX 工作流（何時觸發 skill + 優先序閘門 + 交付前檢查表）。 |
| [`ux/ux-audit-2026-06.md`](ux/ux-audit-2026-06.md) | 前端 UX 稽核報告。 |
