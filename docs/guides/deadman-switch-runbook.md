# Dead-man switch 設定與演練 runbook（維運安全軌 H2）

> **是什麼**：系統死了（電腦當機、Windows 更新重開、斷網、後端崩潰），
> 要有「系統外側」的服務主動通知你。本機發不出「我死了」的通知——
> 所以警報必須掛在外面。本專案用 [healthchecks.io](https://healthchecks.io) 免費版。
>
> **機制**：後端每 `HEARTBEAT_PING_INTERVAL_MIN` 分鐘（預設 30）對你的專屬網址發一個
> GET（`backend/services/heartbeat.py` 的 `ping_deadman`，由 APScheduler 排程）。
> healthchecks.io 超過「period + grace」沒收到 ping → 主動發 email / Discord 警報。
>
> ⚠️ **沒演練過的 dead-man switch 等於沒有。** 設定完成後務必做一次第三節的演練。

---

## 一、設定步驟（一次性，約 10 分鐘）

1. **註冊**：到 https://healthchecks.io 免費註冊（免費版可建 20 個 check，個人用綽綽有餘）。
2. **建 check**：
   - 名稱：`albee-stock-backend`（隨意，認得出來就好）。
   - **Period（期望 ping 間隔）：1 hour**、**Grace（寬限）：1 hour**。
     後端每 30 分鐘 ping 一次 → 漏一兩次不誤報；真死了最慢約 2 小時收到警報。
3. **綁通知管道**（Integrations 頁）：
   - **Email**：預設就有，確認收件人正確。
   - **Discord**（建議，與既有 `notifier` 同一個頻道體驗一致）：
     Integrations → Discord → 授權到你的伺服器頻道即可。
4. **複製 ping 網址**：check 詳情頁的 `https://hc-ping.com/<uuid>`。
5. **填進 `.env`**（**絕不 commit**——`.env` 本來就在 .gitignore）：
   ```
   HEARTBEAT_PING_URL=https://hc-ping.com/你的uuid
   HEARTBEAT_PING_INTERVAL_MIN=30
   ```
6. **重啟後端**，確認 healthchecks.io 的 check 在約 30 分鐘內變成綠色（收到第一個 ping）。

> 心跳「日報」（每天 `HEARTBEAT_HOUR` 時發到 LINE/Discord 的「💓 活著」摘要）
> 與 dead-man ping 是兩件事：日報給人看、ping 給機器看。URL 沒填只關 ping，日報照發。

---

## 二、警報響了怎麼辦（排查順序）

收到「check is DOWN」警報，依序檢查（由最常見到最少見）：

| # | 檢查 | 指令 / 動作 |
|---|------|------------|
| 1 | 電腦活著嗎？ | 人到機器前 / 遠端桌面。死機 → 重開機（開機自啟會把後端帶起來） |
| 2 | 網路通嗎？ | 開瀏覽器隨便打個網站；不通 → 修網路（**注意：斷網期間券商端止損仍有效**——這就是 H1 的價值） |
| 3 | 後端活著嗎？ | 瀏覽器開 `http://127.0.0.1:8000/`（健康檢查端點）。沒回應 → 看下一步 |
| 4 | 開機自啟還在嗎？ | `schtasks /Query /TN AlbeeStockBackend`（工作排程器註冊，見 `scripts/register_autostart.bat`）。不在 → 重新註冊 |
| 5 | 後端起得來嗎？ | 手動雙擊 `start_backend.bat` 看主控台錯誤訊息；常見：`.env` 壞掉、DB 遷移沒跑（`venv\Scripts\alembic.exe upgrade head`） |
| 6 | ping 排程死了（後端活著但 ping 停）？ | 看後端主控台有無 `dead-man ping 失敗` 警告；重啟後端 |

排查完、check 轉回綠色（UP）後，healthchecks.io 會自動發「恢復」通知。

---

## 三、演練（設定完成後做一次；之後**每月一次**）

> 目的：證明「系統死 → 你真的會收到警報」這條鏈每一環都通。

1. 記下現在時間，**手動關掉後端**（關 uvicorn 視窗 / 結束工作管理員裡的進程）。
2. 等 period + grace（約 2 小時）——期間不要碰它。
3. **確認收到** healthchecks.io 的 DOWN 警報（email / Discord）。
4. 重啟後端（雙擊 `start_backend.bat`），確認收到「恢復 UP」通知。
5. 在月曆 / 待辦記下次演練日期。

任何一環沒通（沒收到警報最危險）→ 回第一節逐項檢查設定，修好再演練一次。

---

## 邊界與原則

- **不把後端 port 暴露到公網**：dead-man 是「本機主動向外 ping」，不需要對外開放任何端口；
  UptimeRobot 那種「從外面探測你的 URL」的模式不適用也不該用。
- 出國 / 長時間不在機器旁：dead-man 照常運作，這正是它存在的意義；
  但警報響了沒人能到機器前，**持倉保護靠的是券商端止損（H1）**，兩者是搭配關係。
- healthchecks.io 免費版額度：20 個 check、每 check 100 條 log——本專案只用 1 個，遠夠。
