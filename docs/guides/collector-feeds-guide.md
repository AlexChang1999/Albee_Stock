# 市場蒐集員 feed 設定指南（Phase 12 step-01：collector 通電）

> 把 Phase 10 step-04 蓋好的 RSS 蒐集員正式通電：填 feed、設間隔、驗收行為。
> **預設全關**——`.env` 沒填就完全不跑；關掉後行為與沒裝過一樣。

---

## 一、推薦來源（量化／交易策略 RSS）

> 以下為撰寫時（2026-06）可用的公開 feed，**不保證永久有效**。加任何來源前，
> 先走「二、robots.txt 檢查步驟」自行確認允許抓取。

| 來源 | Feed 網址 | 說明 |
|------|-----------|------|
| Quantocracy | `https://quantocracy.com/feed/` | 量化部落格聚合器，每日精選各家策略文章（一站抵多站）。 |
| Alpha Architect Blog | `https://alphaarchitect.com/feed/` | 因子投資／學術派策略研究，文章品質高。 |
| Quantpedia Blog | `https://quantpedia.com/blog/feed/` | 策略百科官方部落格，常有「某論文策略」摘要。 |

選 2~3 個就好——瓶頸不在素材量，在「證明不是運氣」（OOS 閘淘汰率本來就高）。

## 二、robots.txt 檢查步驟（加新來源前必做）

1. 瀏覽器開 `https://<站台網域>/robots.txt`（例：`https://quantocracy.com/robots.txt`）。
2. 找 `User-agent: *` 區塊底下的 `Disallow:` 清單。
3. 確認 feed 路徑（如 `/feed/`）**不在** Disallow 清單內；整站 `Disallow: /` 就別收。
4. RSS feed 本身就是「請來訂閱」的公開介面，一般都允許；但仍守禮貌：
   - 間隔別低於 60 分鐘（RSS 內容更新沒那麼快，打多了只是騷擾來源）。
   - 蒐集員已內建 User-Agent（`COLLECTOR_USER_AGENT`，預設 `AlbeeStockCollector/1.0`）
     與 15 秒逾時、逐一抓不並發——別改掉這些禮貌設計。

## 三、`.env` 設定範例

```ini
# 逗號或換行分隔多個 feed；留空 = 蒐集員完全關閉
COLLECTOR_RSS_FEEDS=https://quantocracy.com/feed/,https://alphaarchitect.com/feed/

# 掃描間隔（分鐘）；0 = 關閉排程（即使 feeds 有填也不會自動跑）
COLLECTOR_INTERVAL_MIN=60
```

改完重啟後端（`start_backend.bat`）生效。

**關掉就回全關**：把 `COLLECTOR_INTERVAL_MIN` 設回 `0`（或清空 `COLLECTOR_RSS_FEEDS`）
再重啟，系統行為與通電前完全一致——不抓網、不寫表、不通知。已收進收件匣的素材保留不動。

## 四、驗收 runbook（通電後做一次）

1. **跑第一輪**：重啟後端等排程觸發，或直接手動跑一輪：
   ```powershell
   venv\Scripts\python.exe -c "from backend.services.collector import run_collector_scan; run_collector_scan()"
   ```
2. **驗入庫**：開前端「市場蒐集員」頁（CollectorPage），應看到 status=new 的素材。
3. **驗去重**：同指令再跑一輪——素材數不變、不重複通知（upsert 冪等）。
4. **觀察 3~7 天**：每天看一眼收件匣——
   - 素材量：一天幾篇？太多（>50/日）考慮減來源。
   - 垃圾率：廣告／無關文占比？某來源垃圾多就移出 feeds。
   - 例外：後端 log 有未捕捉例外 → 回報修 bug（一 bug 一 commit）。

## 五、邊界（這條線不踩）

- **只收 RSS**——不加 HTML 爬蟲來源、不爬股價（資料一律走既有 `market_data`）。
- 來源打不到 = 跳過 + 下輪再試，**不重試轟炸**（已內建 best-effort）。
- 蒐集員**只收料**：不建策略、不驗證、不部署。後續交給 Phase 12 step-02 探勘橋
  （或人工 strategy-builder）＋既有 OOS 閘。
