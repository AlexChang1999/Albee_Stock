# 雲端 / 地端工作劃分（誰在哪跑、怎麼分工才不打架）

> 機器人後端已 24/7 跑在 Oracle Cloud E2.1.Micro VM（`158.101.127.219`），連同一份
> Neon 雲端 PostgreSQL，與本機 Windows 共用資料。這頁說清楚：**哪些功能在雲端跑、
> 哪些留本機、兩邊怎麼分工才不會互相打架。**
>
> 部署細節見 [`free-vm-deployment.md`](free-vm-deployment.md)（Oracle 開機/裝機/systemd）；
> 搶 A1 大機器見 [`oci-grab-a1.md`](oci-grab-a1.md)。

## A. 一句話原則

**雲端 = 唯一的交易執行者（24/7 不關機）。本機 Windows = 開發工作站（寫策略、跑重回測、看 UI）。**

雲端那台是「正式上工」的機器人；本機是你「研究、寫程式、看盤」的桌子。兩者共用同一份
Neon 資料庫，所以資料天然同步——但**執行交易的排程器只能有一個**（見下方紅線）。

## B. ⚠️ 最重要的紅線：本機與雲端不可同時讓 Bot 進 running 狀態

```
┌─────────────────────────────────────────────────────────────┐
│  危險：兩台機器同時跑「啟用中的 Bot」＝ 重複下單             │
│                                                               │
│  後端一啟動（backend/main.py 的 lifespan）就會自動把所有     │
│  is_active=True 的 Bot 重新掛上排程，每隔 check_interval_sec  │
│  秒自動執行一次。若雲端和本機都開著後端、且 Bot 都 active：  │
│    • 同一個進場訊號會被送兩次（雲端一張、本機一張）          │
│    • 兩邊互相覆蓋追蹤止損的最高價狀態                        │
│    • Paper 模式不燒錢但資料變髒；上了實盤就是真的雙倍下單    │
└─────────────────────────────────────────────────────────────┘
```

**為什麼會這樣**：兩台後端看的是**同一份 Neon DB**、用的是**同一組 Alpaca 金鑰**
（同一個券商帳戶）。它們彼此不知道對方存在，各自照 DB 裡的 Bot 設定下單。

**安全做法（二選一）**：

| 你想做的事 | 怎麼開才安全 |
|------------|--------------|
| 平常（讓機器人自己跑） | **雲端**保持 Bot active 當唯一交易者。本機**不開後端排程**——要看畫面就只開前端（見 E 節）連雲端 IP。 |
| 本機要除錯／改 code 測試 | 先確認雲端那些 Bot 你不介意它繼續跑；本機開後端時**把要測的 Bot 先 stop**，或用不同的 Paper 帳戶金鑰。別讓同一隻 Bot 兩邊都 active。 |

> 白話：**正式跑交易的只准一台**。要嘛雲端、要嘛本機，不要兩個同時 active。
> 日常就讓雲端跑，本機純看 + 開發。

## C. 功能 × 該在哪跑

| 功能 | 雲端 Micro（1GB） | 本機 Windows | 未來 A1（搶到後） |
|------|:---:|:---:|:---:|
| Bot 即時交易監聽（輕量） | ✅ **主場** | ⛔ 別同時 active | ✅ bot 搬過去 |
| 寫／改策略 `.py` 檔（純改 code） | — | ✅ 在這寫，push 後雲端 pull | — |
| 單檔回測 `/backtest` | ⚠️ 可跑但慢 | ✅ 建議 | ✅ |
| 全自動掃描 `/auto-backtest`、領導股回測 | ❌ **OOM 風險** | ✅ 建議 | ✅ |
| Monte Carlo 壓力測試 | ⚠️ 尚可（numpy 快） | ✅ | ✅ |
| Screener 海選 `/ai-recommendations` | ⚠️ 需 LLM、偏重 | ✅ | ✅ |
| LLM 思考助手（Ollama 本機腦） | ❌ **1GB 跑不動** | ✅ 本機 Ollama | ✅ A1 RAM 夠可裝 |
| 前端 UI Dashboard | ❌ 未部署 | ✅ `npm run dev` 連雲端 IP | 之後可部署 |
| explorations 檔案記憶 | ⚠️ 各機獨立檔案 | ✅ 進 git 才同步 | — |

圖例：✅ 適合／推薦　⚠️ 可跑但有代價　❌ 不要在這跑　⛔ 安全紅線

## D. 回答你的疑問：「我是不是只能在我這台電腦跑策略 / 回測？」

**不是只能在本機，但有分工：**

1. **寫新策略 = 改程式碼**。在**本機**用編輯器寫 `backend/strategies/<name>.py`，
   `git push`；雲端那台 `git pull` + 重啟服務（`sudo systemctl restart albee-backend`）
   就生效。雲端不是拿來「寫」程式的地方，是「跑」的地方。

2. **回測可以在任何跑得動後端的機器上跑**，但**重運算建議放本機或未來的 A1**：
   - 單檔 `/backtest`：雲端勉強能跑，慢。
   - 全自動掃描 `/auto-backtest`、領導股回測：8 種策略 × 多組參數逐組回測，**極吃 RAM，
     1GB 的 Micro 很可能 OOM（記憶體不足被系統砍掉）**。這類請在本機跑。

3. **思考助手（LLM）目前只有本機有腦**：雲端 Micro 1GB 裝不下 Ollama，部署時已把
   `LLM_BASE_URL` 清空停用（呼叫會優雅回 400，不會卡住別的功能）。要在雲端用助手，
   得等搶到 A1（RAM 夠）裝 Ollama，或把 `LLM_BASE_URL` 改指向雲端 LLM 供應商
   （Gemini／Groq 等）並開 `LLM_ALLOW_CLOUD=true`。

## E. 本機前端連雲端後端（用瀏覽器看雲端機器人）

前端預設連 `http://127.0.0.1:8000`（本機後端）。要讓本機瀏覽器看**雲端**機器人，
在 `frontend/` 建一個 `.env.local`（git 會忽略，不進版控）：

```
VITE_API_URL=http://158.101.127.219:8000
```

然後 `npm run dev`，前端就改連雲端後端。這樣本機**不必開後端排程**也能看雲端的帳戶、
持倉、交易紀錄——既能看畫面、又不會踩到 B 節的雙開紅線。

> 注意：前端只讀得到 `VITE_` 開頭的環境變數，其他變數不會注入前端。

## F. 雲端 Micro 健康監控（先觀察、真 OOM 再減載）

目前選擇**先維持現狀**（不關常駐機會掃描），靠下面指令盯著。SSH 進 VM 後跑：

```bash
# 1. 看 RAM 與 swap 用量（swap 常滿 = 記憶體吃緊）
free -h

# 2. 看後端有沒有被 OOM 砍掉重啟（找 "Killed" / "Out of memory" / 頻繁 restart）
journalctl -u albee-backend -n 50 --no-pager

# 3. 確認服務還活著（要看到 active (running)）
systemctl status albee-backend --no-pager
```

**判讀**：
- `free -h` 的 swap 偶爾用一點正常；**長期接近滿、或 `journalctl` 看到 OOM kill / 服務反覆重啟** → 該減載。
- 減載做法：編輯 VM 上的 `.env`，把常駐機會掃描關掉——
  ```bash
  # 在 ~/Albee_Stock/.env 設這行（0 = 關掉盤中常駐海選掃描）
  SCAN_INTERVAL_MIN=0
  sudo systemctl restart albee-backend
  ```
  關掉後 Micro 只跑輕量的 Bot 交易監聽，重運算（掃描／領導股回測／海選）全部回本機或 A1 跑。

> 真正治本是搶到 A1（4 OCPU / 24GB RAM）把機器人搬過去，重運算就不怕 OOM。
> 搶 A1 步驟見 [`oci-grab-a1.md`](oci-grab-a1.md)。
