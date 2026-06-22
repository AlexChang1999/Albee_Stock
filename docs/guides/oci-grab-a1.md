# 搶 A1.Flex runbook（用第二台 Micro 掛機重試）

> A1.Flex（Ampere ARM，免費可達 4 OCPU / 24GB RAM）常常 `Out of host capacity`——
> 容量被搶光，要靠**重試腳本掛機等別人釋出**。這頁帶你開**第二台 E2.1.Micro**、
> 裝 OCI CLI、掛 [`scripts/grab-a1.sh`](../../scripts/grab-a1.sh) 自動搶。
>
> 搶到後把機器人搬過去的部署流程，沿用既有 [`free-vm-deployment.md`](free-vm-deployment.md)
> 與第一台 Micro 的部署經驗（記憶 `oracle-micro-vm-deploy`）。

## 為什麼用第二台 Micro 掛機，不用本機

重試腳本要 **24/7 不停試**。跑在會關機的本機 Windows，一關機就停、搶不到。
Oracle 免費額度允許 **2 台 E2.1.Micro 並存**，所以開第二台專門掛搶 A1，
不干擾第一台正在跑的交易 bot。搶到 A1 後，第二台 Micro 可以留著當備援或關掉。

## 步驟總覽

```
開第二台 Micro → 裝 OCI CLI → 設 API 金鑰 → 蒐集 OCID → 掛 grab-a1.sh → 搶到搬 bot
```

### 1. 開第二台 E2.1.Micro（Ubuntu）

Console → Compute → Instances → Create instance：
- Image：Ubuntu（與第一台一致，習慣的環境）
- Shape：`VM.Standard.E2.1.Micro`（Always Free 標章那個）
- 網路：可沿用既有 VCN／subnet
- SSH key：上傳你的 public key（搶 A1 與這台登入都會用到金鑰）

> ⚠️ 安全：真實金鑰、OCID、密碼**絕不貼進對話**。下面凡是 `<...>` 的都你自己填。

### 2. 裝 OCI CLI（在第二台 Micro 上）

SSH 進第二台 Micro，跑官方安裝腳本：

```bash
bash -c "$(curl -L https://raw.githubusercontent.com/oracle/oci-cli/master/scripts/install/install.sh)"
# 一路同意預設即可；裝完重開 shell 或 source ~/.bashrc
oci --version    # 印出版本 = 裝好了
```

### 3. 設 API 金鑰（讓 CLI 能呼叫你的 Oracle 帳戶）

```bash
oci setup config
```

它會問你 user OCID、tenancy OCID、region，並**自動產一對 API 簽章金鑰**
（預設在 `~/.oci/`）。產完後到 Console：

`右上頭像 → My profile → API keys → Add API key → 貼上剛產的 public key`
（`~/.oci/oci_api_key_public.pem` 的內容，或直接上傳該檔）。

驗證能通：

```bash
oci iam region list    # 有回 region 清單 = 金鑰設定成功
```

### 4. 蒐集要帶進腳本的 OCID

`grab-a1.sh` 需要這些 ID（Console 各頁面右鍵複製 OCID，或用 `oci` 查）：

| 變數 | 哪裡拿 |
|------|--------|
| `COMPARTMENT_ID` | Console → Identity → Compartments（通常用 root tenancy 那個） |
| `SUBNET_ID` | 你 VCN 的 subnet 詳情頁 |
| `IMAGE_ID` | 要裝的 A1 Ubuntu image OCID：`oci compute image list --compartment-id <C> --operating-system "Canonical Ubuntu" --shape VM.Standard.A1.Flex`（挑最新一筆的 `id`） |
| `SSH_AUTHORIZED_KEYS_FILE` | A1 開機要塞的 public key 檔路徑（如 `~/.ssh/id_rsa.pub`） |
| `ADS`（AD 清單） | `oci iam availability-domain list`（把回傳的 `name` 填進腳本陣列） |

> A1 容量在不同 availability domain（AD-1/2/3）各自獨立，腳本會輪流試每個 AD，
> 哪個 AD 有空位就搶哪個。

### 5. 掛上重試腳本

把 repo 裡的 [`scripts/grab-a1.sh`](../../scripts/grab-a1.sh) 複製到第二台 Micro
（`git clone` 或 `scp`），編輯**檔頭變數區**填入第 4 步的 OCID，然後掛背景：

```bash
chmod +x grab-a1.sh
nohup ./grab-a1.sh > grab-a1.log 2>&1 &   # 背景掛機，斷 SSH 也續跑
tail -f grab-a1.log                        # 看進度（Ctrl-C 只是停看，腳本仍在跑）
```

腳本每約 75 秒輪一輪所有 AD 試一次 `instance launch`：
- `Out of host capacity` → 記 log、繼續等。
- 成功 → 印出新 instance 的 OCID 並停止迴圈。

> ⚠️ 重試間隔保持 **60–90 秒**（腳本預設 75s），別改太短——太密集打 API 可能被判濫用。

### 6. 搶到 A1 之後

1. Console → Instances 看到新 A1 instance `running`，複製它的 Public IP。
2. 照第一台 Micro 的部署流程把機器人搬過去（裝 venv、`git clone`、scp `.env`、
   建 `albee-backend` systemd 服務）。A1 與 Micro 免費方案可並存。
3. **搬機後 `ALLOW_LIVE_TRADING` 仍維持 `false`**（Paper 模式），確認一切正常再談實盤。
4. A1 RAM 夠（給 8–16GB），可順便 `ollama serve` 讓雲端思考助手有腦
   （把 A1 `.env` 的 `LLM_BASE_URL` 指回 `http://localhost:11434/v1`）。
5. **切換交易執行者時記得守紅線**：A1 開始跑交易後，把第一台 Micro 的 Bot 全 stop
   或關掉它的後端，避免兩台同時下單（見 [`cloud-local-division.md`](cloud-local-division.md) B 節）。
