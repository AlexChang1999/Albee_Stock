# CICD 上雲 runbook — 讓代碼真的到 VM + 自動部署

> 對應事件：2026-06-16 發現「CICD 已建好但代碼從沒上雲」。
> CI 驗證關卡（test job）會過，但 CD 部署（deploy job）因 **GitHub Secrets 沒設** 而失敗，
> VM 一直跑舊碼。這份是把代碼弄上雲 + 修好自動部署管線的完整步驟。

## 背景（真相）

- ✅ 代碼在遠端 `main`（PR #44 / #45 已 merge，commit `9ab21a3`）。
- ✅ CI 驗證關卡（`test` job）通過。
- ❌ CD 部署（`deploy` job）**失敗** → VM 從沒拿到新碼。
  - 失敗 run：`27591734193`，jobs = `test: success` / `deploy: failure`。
  - 根因：GitHub Secrets `VM_HOST` / `VM_USER` / `VM_SSH_KEY` **一個都沒設**
    → `appleboy/ssh-action` 連不上 VM → deploy job 直接掛。

> ⚠️ 下面的 SSH / 設 Secret / curl 都要在**你本機**跑（VM 私鑰只在你本機，Claude 無法代跑）。
> 在 Claude Code session 裡可用 `! ` 前綴跑，輸出會回到對話讓我幫判讀。

---

## ⚠️ 關掃描不是改 `.env`（最容易踩的坑）

`scan_interval_min` **存 Neon DB**（`backend/models/automation_config.py`），
只有「DB 還沒這列」時才用 env `SCAN_INTERVAL_MIN` 當種子（`backend/services/automation_config.py`）。
Neon 共用、該列早已存在 → **VM 改 `.env` 不會生效**。

正確關法（即時重掛、免重啟，`backend/routers/automation.py` 的 PUT `/automation`）：

```bash
curl -X PUT http://127.0.0.1:8000/automation \
  -H "Content-Type: application/json" \
  -d '{"scan_interval_min": 0}'
# 0 = 關掉常駐探勘排程；全域生效（Neon 共用，本機排程掃描也一起關）
```

- 重運算改用 **on-demand**：本機前端按「立刻掃一輪」(`run_opportunity_scan`)，
  在本機 process 跑、不上 VM → 符合「重運算留本機」（避免 Micro 1GB 跑海選 OOM）。
- 也可直接用前端 `AutomationPanel` 把間隔改 0，免打 curl。

---

## 步驟 1（最快、止血）：手動部署一次，把代碼弄上 VM

```bash
ssh ubuntu@158.101.127.219 "cd ~/Albee_Stock && bash scripts/deploy.sh main"
```

`scripts/deploy.sh` 會：記住舊 commit → `git fetch + reset --hard origin/main` →
`venv/bin/pip install` → `venv/bin/alembic upgrade head` → `sudo systemctl restart albee-backend`
→ `curl` 健康檢查（失敗自動 `git reset` 回滾 + 重啟）。跑完 VM 就是新碼。

> 前提：先做步驟 2c（免密碼 sudo 重啟），否則 `sudo systemctl restart` 會卡密碼提示。

---

## 步驟 2：補 Secrets + VM 權限，讓以後 push `main` 自動部署

### 2a. VM 上產部署專用 SSH 金鑰（兩台 VM 各一次）

```bash
ssh-keygen -t ed25519 -f ~/.ssh/gh_deploy -N "" -C "github-actions-deploy"
cat ~/.ssh/gh_deploy.pub >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
cat ~/.ssh/gh_deploy            # 印「私鑰」全文，下一步貼進 VM_SSH_KEY
```

### 2b. 設 GitHub Secrets（gh CLI，在本機 repo 目錄）

```bash
gh secret set VM_HOST --body "158.101.127.219"
gh secret set VM_USER --body "ubuntu"
gh secret set VM_SSH_KEY < ~/.ssh/gh_deploy      # 或把 2a 印出的私鑰存檔再導入
```

TrumpTrueSocial_Bot repo 同樣設一組（切到該 repo 目錄再跑同三條，`VM_HOST` 換 trump VM IP）。

### 2c. VM 給免密碼 sudo 重啟（deploy.sh 非互動需要）

```bash
# Albee VM：
echo "$USER ALL=(root) NOPASSWD: /bin/systemctl restart albee-backend" | sudo tee /etc/sudoers.d/albee-deploy
# Trump VM：
echo "$USER ALL=(root) NOPASSWD: /bin/systemctl restart trump-monitor" | sudo tee /etc/sudoers.d/trump-deploy
```

### 2d. 重跑失敗的部署（Secret 設好後）

```bash
gh run rerun 27591734193 --job deploy
# 或推任何 commit 到 main 觸發新一輪
```

---

## 步驟 3：部署後關 VM 常駐掃描（防 Micro OOM）

代碼上 VM、後端起來後，打一次（見上「關掃描不是改 .env」）：

```bash
curl -X PUT http://127.0.0.1:8000/automation -H "Content-Type: application/json" -d '{"scan_interval_min": 0}'
```

之後本機要掃就按「立刻掃一輪」。

---

## 步驟 4：驗 VM 真的跑新碼 + 單實例

```bash
ssh ubuntu@158.101.127.219
cd ~/Albee_Stock
git log --oneline -1                 # 應為 9ab21a3（或更新）
venv/bin/alembic current             # 對 venv/bin/alembic heads，含 a8f1c2d3e4b5（唯一鍵 migration）
journalctl -u albee-backend -n 30    # 看「排程 leader / 沒搶到鎖」字樣 = 選主鎖生效
curl -fsS http://127.0.0.1:8000/     # 回 JSON = 健康
ps aux | grep -c "[u]vicorn"         # VM 只一個
```

地端若也開後端連同一 Neon → 排程器選主鎖（`backend/services/scheduler_lock.py`）會讓其中一個
只當唯讀 API、不重複推播（log 可見）。雙開排程紅線見
[`cloud-local-division.md`](cloud-local-division.md)。

---

## 相關檔案

- `scripts/deploy.sh` — VM 端部署腳本（拉碼 / 遷移 / 重啟 / 健康檢查 / 失敗回滾）。
- `.github/workflows/ci.yml` — 兩段式 CI（test gate）→ CD（push main 自動 SSH 部署）。
- `backend/services/scheduler_lock.py` — Neon advisory lock 排程器選主（防雙實例重發）。
