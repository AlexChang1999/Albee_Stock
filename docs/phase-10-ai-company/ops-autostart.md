# Phase 10 step-07 — 開機常駐化（Windows 自啟）運維手冊

> 純 ops，**零交易邏輯改動**。解決「APScheduler 排程在記憶體裡、關掉 app 就停」的落差：
> 讓電腦開機（登入）後，後端自動起來，常駐跑 Bot 監聽 + 盤前自動部署 + 機會探勘掃描。
>
> ⚠️ **常駐 ≠ 開實盤。** 常駐跑的仍是 **Paper（模擬）**。真錢仍須實盤雙閘
> （`ALPACA_BASE_URL` 實盤 + `ALLOW_LIVE_TRADING=true`）+ 董事會核准（step-06），本步完全不碰。

---

## 一、它怎麼運作（為什麼這樣就夠）

開機 → 登入 → Windows「工作排程器」觸發 `start_backend.bat` → uvicorn 起 FastAPI →
`backend/main.py` 的 `lifespan` 啟動時自動做三件事（**既有，不需新寫**）：

1. `_resume_active_bots()`：把 DB 裡 `is_active=True` 的 Bot 用各自的 `check_interval_sec` 重新掛回排程。
2. `schedule_auto_deploy(scan_hour)`：掛上每日盤前自動部署 cron。
3. `schedule_opportunity_scan(scan_interval_min)`：掛上盤中常駐機會探勘的週期 job（step-02）。

所以「開機就一直跑」只缺最後一哩：**開機自動把後端拉起來**——這就是本步用「工作排程器」補的。
不做 Windows 系統服務 / NSSM（多一層維運複雜度；登入觸發的排程工作已足夠本機單人使用）。

---

## 二、安裝（一次性）

1. 確認已能正常手動啟動：雙擊根目錄 `start_backend.bat`，瀏覽器開 <http://127.0.0.1:8000/docs> 有頁面。
2. 對 `scripts\register_autostart.bat` 按右鍵 → **以系統管理員身分執行**（建立排程工作需要權限）。
   - 成功會印「已註冊。下次登入 Windows 會自動啟動後端。」
   - 它註冊的工作名稱是 **`AlbeeStockBackend`**，觸發條件 `ONLOGON`（目前使用者登入時）。
3. 立刻測試（不必登出）：在終端機跑
   ```
   schtasks /Run /TN "AlbeeStockBackend"
   ```
   會跳出一個跑著 uvicorn 的視窗。

---

## 三、驗收 checklist（手動，無 pytest）

登入（或 `schtasks /Run`）後，逐項確認：

- [ ] 後端有起：瀏覽器開 <http://127.0.0.1:8000/> 有 JSON 回應（或 `/docs` 有頁面）。
- [ ] 帳戶端點可回：<http://127.0.0.1:8000/account>（離線/無金鑰會 best-effort，不必有真資料）。
- [ ] 啟用中的 Bot 有被接回：start_backend 視窗印出「♻️ 已恢復 N 個…」之類訊息；
      `/bots` 看得到 `is_active=true` 的 Bot。
- [ ] 機會探勘 job 有掛上：盤中時段每隔 `scan_interval_min` 分鐘，視窗會有掃描/通知輸出；
      `/opportunities` 會逐步累積候選。
- [ ] 因子報表有累積（step-03）：盤中跑幾輪後 `/factors` 有資料。

---

## 四、常見操作

| 想做的事 | 指令 / 動作 |
|----------|-------------|
| 立刻手動觸發一次 | `schtasks /Run /TN "AlbeeStockBackend"` |
| 看工作狀態 | `schtasks /Query /TN "AlbeeStockBackend" /V /FO LIST` |
| 暫停自動啟動 | `schtasks /Change /TN "AlbeeStockBackend" /DISABLE` |
| 恢復自動啟動 | `schtasks /Change /TN "AlbeeStockBackend" /ENABLE` |
| 永久移除 | 以系統管理員執行 `scripts\unregister_autostart.bat` |
| 停掉正在跑的後端 | 在那個 uvicorn 視窗按 `Ctrl+C`（或關閉視窗） |

---

## 五、失敗排查

- **登入後沒自動起**：先用 `schtasks /Query` 看工作在不在、有沒有被 `/DISABLE`；
  再手動雙擊 `start_backend.bat` 確認本身能跑（venv / .env 是否就緒）。
- **視窗一閃就關**：多半是 `start_backend.bat` 自己的前置檢查沒過（找不到 venv 或 .env）。
  先照 `setup.bat` 把環境補齊。
- **看 log**：目前後端 log 只輸出到那個 console 視窗（無寫檔）。需要長期保存 log 屬後續優化，
  不在本步範圍。
- **權限不足建不了工作**：`register_autostart.bat` 必須「以系統管理員身分執行」。

---

## 六、明確界線（不要做）

- **不**做成 Windows 系統服務 / NSSM 等重維運方案（工作排程器夠用）。
- **不**在開機腳本裡塞任何交易邏輯——它只負責「把後端拉起來」。
- **不**因為常駐就放寬安全閥：真錢永遠是「實盤雙閘 AND 董事會核准」說了算。
