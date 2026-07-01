# 免費 VM 常駐部署指南（Phase 12 觀察期專用）

> 目的：Phase 12 step-05 兩週觀察需要一台**常駐機器**連跑 collector + 探勘橋（Ollama）+
> auto_validate。家用電腦靠「一天開機一次 + 開機補跑」也能跑，但要 24/7 不間斷、
> 不佔自己電腦，免費雲端 VM 是更穩的選項。本指南：選哪家、怎麼開通、Linux 裝機、
> 兩個 Linux 限定坑、LLM 備援方案。
>
> 真實金鑰只進 VM 上的 `.env`，**絕不** commit；交易一律 Paper、不碰實盤雙閘。

---

## 1. 為什麼選 Oracle Cloud（方案比較）

關鍵限制：探勘橋每天要跑**本機 Ollama llama3.1 8B**，模型約 5GB、推論需要約
6~8GB RAM——傳統「免費層小 VM」（1GB RAM）根本載不起來。各家現況（2026-06）：

| 方案 | 規格 | 免費期限 | 跑得動 Ollama 8B？ |
|------|------|----------|--------------------|
| **Oracle Cloud Always Free — Ampere A1**（推薦） | 最高 4 OCPU ARM / 24GB RAM / 200GB 碟 | **永久**（非試用） | ✅ 唯一可以（CPU 推論，每日批次夠用） |
| Azure 免費帳戶 B1s | 1 vCPU / 1GB | 12 個月 | ❌ |
| AWS 免費方案（2025 年中改制） | credits $100~200 | 6 個月（已非 12 個月 750h 制） | ❌（credits 撐不起 8GB 機） |
| GCP Always Free e2-micro | 0.25 vCPU / 1GB | 永久 | ❌ |

結論：**要免費跑完整管線（含 Ollama）只有 Oracle A1 一條路**。搶不到 A1 容量時，
退而求其次用任何小 VM + 雲端免費 LLM（見 §6 備援）。

> ARM 相容性：本專案後端純 Python（pandas/numpy/fastapi/alpaca-py 都有 ARM wheel），
> Ollama 官方支援 ARM64，無相容性問題。

---

## 2. Oracle 開通步驟（一次性，人工操作）

1. 到 <https://www.oracle.com/cloud/free/> 註冊（需信用卡驗證身分，**不會扣款**；
   Always Free 資源永遠免費，不升級付費方案就不可能產生費用）。
   - Home Region 選定後**不能改**，建議選 `Japan East (Tokyo)` 或 `Singapore`（離台灣近）。
2. 建 instance：Compute → Instances → Create Instance
   - Image：**Ubuntu 24.04**（aarch64）
   - Shape：**Ampere → VM.Standard.A1.Flex**，拉滿 **4 OCPU / 24GB RAM**
     （Always Free 額度就是 4 OCPU + 24GB，一台用滿最划算）
   - Boot volume：預設 47GB 夠用（模型 5GB + 程式 + DB 綽綽有餘）
   - SSH key：上傳自己的公鑰（**只用金鑰登入**，不開密碼）
3. **A1 容量搶不到**（`Out of capacity` 錯誤）的應對：
   - 換同 region 別的 Availability Domain 再試
   - 降規格試 2 OCPU / 12GB（一樣跑得動 8B 模型）
   - 寫個重試（Oracle 容量隨時釋出，熱門區常要試幾天）；等不及就先用 §6 備援方案開跑
4. **網路安全（重要）**：
   - VCN security list 預設只開 22（SSH）——**維持原樣，不要開 8000 對公網**。
     後端 API 無認證機制，暴露公網等於任何人都能操作你的 Bot。
   - 看前端/API 一律走 SSH tunnel（見 §5）。

---

## 3. Linux 裝機（後端 + 排程管線）

SSH 進 VM 後（`ssh ubuntu@<VM_IP>`）：

```bash
# 0. 時區（必做！見 §4 坑 1）
sudo timedatectl set-timezone Asia/Taipei

# 1. 系統依賴（Ubuntu 24.04 內建 python3.12，跑本專案沒問題）
sudo apt update && sudo apt install -y python3-venv python3-pip git

# 2. 拉程式 + 建環境
# （repo 是私有的：先到 GitHub → Settings → Developer settings → Fine-grained tokens
#   建一支「只能讀這個 repo」的 token，clone 時當密碼用；token 跟金鑰一樣不落檔、不 commit）
git clone https://github.com/AlexChang1999/Albee_Stock.git && cd Albee_Stock
python3 -m venv venv
venv/bin/pip install -r requirements.txt

# 3. 填 .env（必填項照 backlog D 觀察期 checklist，連結見下）
cp .env.example .env && nano .env

# 4. 建資料庫（DB 用 VM 本機 SQLite 即可；要與家裡共看才接 Neon，見下）
venv/bin/alembic upgrade head

# 5. 手動驗通一次（金鑰有效才往下）
venv/bin/python backend/test_connection.py
```

- `.env` 必填清單**不重抄**，照 [`../remaining-work-backlog.md`](../remaining-work-backlog.md)
  「D 項 → 觀察期開跑前 checklist」逐項填（Alpaca 金鑰、feeds、兩個 ENABLED 開關、LLM、通知）。
- DB：單機觀察用預設 SQLite 就好。想在家裡電腦同步看資料，再照
  [`setup-postgres-sync.md`](setup-postgres-sync.md) 接 Neon 免費 PG，兩邊 `.env` 填同一個
  `DATABASE_URL`。
- 前端不用裝在 VM 上（見 §5）。

### Ollama（探勘橋的 LLM）

```bash
curl -fsSL https://ollama.com/install.sh | sh   # 官方腳本，自動裝成 systemd 服務、開機自啟
ollama pull llama3.1                             # 約 5GB
ollama run llama3.1 "hi"                         # 驗通（CPU 推論慢是正常的，每日批次夠用）
```

---

## 4. 兩個 Linux 限定坑（不處理就「以為在跑其實沒跑」）

### 坑 1：時區——排程時刻會整個錯位

APScheduler 的每日 cron 用**伺服器本地時間**，雲端 VM 預設 UTC。不改時區的話
`DISCOVERY_HOUR=7` 會在台灣時間**下午 3 點**才跑，整條管線時序亂掉。
§3 第 0 步的 `timedatectl set-timezone Asia/Taipei` 就是在堵這個，裝完用 `date` 確認。

### 坑 2：看門狗——`start_backend.bat` 是 Windows 的，Linux 用 systemd

`.bat` 的看門狗迴圈在 Linux 沒得跑；systemd 的 `Restart=always` 就是看門狗
（開機自啟 + 崩潰 10 秒自動重啟，搭配既有 `CATCHUP_ON_BOOT` 重啟即接回當日管線）。

建 `/etc/systemd/system/albee-backend.service`：

```ini
[Unit]
Description=Albee Stock backend (FastAPI + APScheduler)
After=network-online.target ollama.service
Wants=network-online.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/Albee_Stock
ExecStart=/home/ubuntu/Albee_Stock/venv/bin/uvicorn backend.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now albee-backend     # 開機自啟 + 立即啟動
systemctl status albee-backend                # 確認 active (running)
journalctl -u albee-backend -f                # 看後端 log（等同看 uvicorn 主控台）
```

注意 `--host 127.0.0.1`：只綁本機，配合 §2 的「不開 8000 對公網」雙保險。
（uvicorn 在 systemd 下不要加 `--reload`——檔案監看在伺服器上沒意義還耗資源。）

### 政治員 Discord bridge（有設 `POLITICAL_DISCORD_TOKEN` 才建）

`political_watcher` 是**獨立進程**，不內嵌在 FastAPI——必須另建 service，否則重開機後橋斷線、事件停更。

```ini
# /etc/systemd/system/albee-political-watcher.service
[Unit]
Description=Albee Political Watcher (Discord bridge)
After=network-online.target albee-backend.service
Wants=network-online.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/Albee_Stock
ExecStart=/home/ubuntu/Albee_Stock/venv/bin/python3 -m backend.bots.political_watcher
Restart=on-failure
RestartSec=30
StandardOutput=journal
StandardError=journal
SyslogIdentifier=albee-watcher

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now albee-political-watcher
journalctl -u albee-political-watcher -f   # 看連線 log，成功顯示 "connected to Gateway"
```

**前提**：`.env` 必須先設好 `POLITICAL_DISCORD_TOKEN`、`POLITICAL_CHANNEL_ID`、`POLITICAL_ENABLED=true`。
沒設 token → watcher 會印出指引後退出（service 會 restart-on-failure 循環，要先填好 token 再啟動）。

---

## 5. 從自己電腦看戰情頁（SSH tunnel）

前端留在自己電腦跑，API 走 SSH 隧道接 VM：

```powershell
# 自己電腦上：把 VM 的 8000 映到本機 8000（開著這個視窗隧道才活著）
ssh -L 8000:127.0.0.1:8000 ubuntu@<VM_IP>

# 另開視窗照常啟動前端（frontend/.env 的 VITE_API_URL 維持 http://127.0.0.1:8000）
start_frontend.bat
```

開 `http://localhost:5173` 就是 VM 上的戰情頁；`http://127.0.0.1:8000/docs` 是 VM 的 API 文件。
日常其實不用一直開隧道——心跳日報（Discord/LINE）+ healthchecks.io 警報就夠盯了，
想看漏斗數字再開。

---

## 6. 備援：A1 搶不到時，小 VM + 雲端免費 LLM

A1 一直 `Out of capacity`（或想先開跑不等容量）時：任何 1GB 小 VM（Azure B1s 12 個月 /
GCP e2-micro 永久）都跑得動**除了 Ollama 以外**的整條管線——探勘橋的 LLM 改走雲端免費層。

`.env` 改三行（`.env.example` 的 Groq/Gemini 段就有範本）：

```ini
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_API_KEY=你的_Groq_key            # https://console.groq.com 免費申請
LLM_MODEL=llama-3.3-70b-versatile
LLM_ALLOW_CLOUD=true                  # 外送閘：明確同意才打開
```

**邊界聲明（已於 2026-06-12 拍板）**：

- 可接受外送的：discovery 探勘橋處理的 **collector 公開 RSS 素材**（文章標題/摘要，
  本來就是公開資訊）。
- 要知道的代價：`LLM_ALLOW_CLOUD=true` 是**整機開關**——這台 VM 上思考助手等
  所有 LLM 呼叫都會走雲端。所以**策略私有資料的深度探討（探討/檢討檔案記憶）
  留在自己電腦的本機 Ollama 環境做**，VM 只負責探勘管線。
- 1GB 小 VM 跑回測（auto_validate / 領導股回測）較吃力：把
  `AUTO_VALIDATE_BATCH_SIZE` 降到 1~2、`LEADER_BACKTEST_SYMBOLS` 砍到 2~3 檔，
  或乾脆 `LEADER_BACKTEST_ENABLED=false`（觀察期主角是探勘漏斗，不是領導股紀錄）。

---

## 7. 開跑驗收（接回既有 checklist）

裝完照 [`../remaining-work-backlog.md`](../remaining-work-backlog.md) D 項
「**4. 串接驗通**」手動各跑一輪 collector / discovery / auto_validate（指令把
`venv\Scripts\python.exe` 換成 `venv/bin/python`），然後做「**5. 起跑儀式**」：
快照 `discovery_funnel` JSON 進
[`../history/phase-12-strategy-discovery/review-e2e.md`](../history/phase-12-strategy-discovery/review-e2e.md)、
填起迄日、判準凍結，開始 14 天觀察。

順手把 H2 欠的 dead-man 演練補了：healthchecks.io ping URL 填 `HEARTBEAT_PING_URL`，
照 [`deadman-switch-runbook.md`](deadman-switch-runbook.md) 停後端 2 小時驗警報
（`sudo systemctl stop albee-backend`，驗完記得 `start` 回來）。VM 是 24/7 常駐，
正是 dead-man switch 發揮價值的場景。
