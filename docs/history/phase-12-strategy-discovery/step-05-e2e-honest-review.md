# Step 05 — 端到端驗收 + 誠實去留檢討

## 原目標錨點
README 伍 Phase DoD 第 5 條：自動化管線要用數據證明自己值得活著，證明不了就降級。
對齊 Phase 7「真資料下無 OOS 加分就砍」鐵律——這次砍的對象是「整條管線的排程」。

## 涉及檔
- 無新程式（本步是驗收 + 文件）
- 本資料夾新增 `review-e2e.md`（驗收紀錄）
- `docs/remaining-work-backlog.md`：D 項標記完成/降級結論
- `CHANGELOG.md`

## Step
1. 全開（collector + discovery + auto_validate）連跑 **兩週**，期間不手動干預管線。
2. 記錄漏斗數據：raw 收料量、candidate 產量、OOS 通過率（validated/candidate）、
   人工晉升量（curated 增量）、垃圾率。
3. 對照基準：同期 `optimizer` 既有網格掃描的 OOS 通過率。
4. 結論三選一，寫進 review-e2e.md：
   - **留**：LLM 提案通過率 ≥ 網格基準、且 curated 有增量 → 管線常開。
   - **降級**：通過率低但素材有閱讀價值 → 排程關閉、collector 留著當人工靈感收件匣（回到 Phase 10 狀態）。
   - **砍**：素材垃圾率高 + 零通過 → 關 feeds，記錄教訓。
5. 不論結論為何，更新 README 文件狀態（藍圖 → 已完成/已降級）。

## DoD
- review-e2e.md 含上述全部數據與結論；backlog/CHANGELOG 同步。
- 若降級/砍：關閉後回歸測試綠（行為 = 開工前）。

## 邊界
- 兩週數據不夠下定論時，寫「延長觀察 + 截止日」，不無限期掛著。
- 不准為了讓管線「看起來有用」調鬆 OOS 門檻（評估期判準凍結）。
