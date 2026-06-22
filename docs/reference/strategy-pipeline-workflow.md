# 策略探勘工作流：11 模組怎麼串成一條水管

> 操作者視角。把側欄 11 個頁面，照「素材怎麼變成上線策略」的順序排好，講清楚
> 每一站「誰餵料給誰、人要在哪出手」。架構/資料流 Mermaid 圖看
> [`workflow-diagrams.md`](workflow-diagrams.md)；單頁用途看 [`frontend-pages-map.md`](frontend-pages-map.md)。

## 一張圖看懂主水管

```
 進料                自動處理（修品質漏洞後可信）        人在迴路        部署
┌─────────┐  ┌──────────────┬───────────────┐  ┌──────────┐  ┌────────┐
│市場蒐集員│→ │  AI 探勘      │   進化實驗室   │→ │策略知識庫 │→ │自動化   │
│  RSS    │  │（探勘橋 LLM   │（OOS 閘自動驗證│  │（人晉升   │  │模式 B   │
│         │  │  產候選）     │  validated）   │  │ curated）│  │Paper Bot│
└─────────┘  └──────────────┴───────────────┘  └──────────┘  └────────┘
     │                                                              │
     └─ 政治專討員＝風險煞車（只擋進、不猜方向）                      ▼
                                                              交易紀錄＝結果
       旁路（隨時查）：回測工具 / 回測歷史 / 策略方案 / 決策審計 / 探討檢討
```

## 11 模組各站職責

| 站別 | 側欄頁 | 在水管哪段 | 自動 / 人工 | 餵給下一站什麼 |
|------|--------|-----------|------------|----------------|
| 進料 | **市場蒐集員** `/collector` | 收 RSS 素材 → 收件匣（status=new） | 自動（排程，預設關） | raw 素材給探勘橋 |
| 進料 | **AI 探勘** `/ai-explore` | 量能→情緒→EV 海選現有標的 | 自動（另一條進料） | 推薦清單（可直接開 Bot）|
| 處理 | **進化實驗室** `/evolution` | 探勘橋（raw→候選）＋ OOS 自動驗證 | 自動 | validated 候選給知識庫 |
| 收口 | **策略知識庫** `/library` | candidate→validated→**curated** 排行 | **人工晉升 curated** | curated 給自動化部署 |
| 旁路 | **策略方案** `/presets` | 存參數組合、一鍵回測 | 人工 | 方案給回測 / 開 Bot |
| 旁路 | **回測工具** `/backtest` | 手動單跑 / 全自動掃描 / 蒙地卡羅 | 人工 | 結果存進回測歷史 |
| 旁路 | **回測歷史** `/backtest-runs` | 依 EV 排序的歷次回測 | 自動存查 | 給人挑冠軍 |
| 旁路 | **決策審計** `/decisions` | 每筆決策（含觀望）落 log | 自動 | 事後查驗用 |
| 旁路 | **探討檢討** `/explorations` | 思考助手的設計/檢討檔案記憶 | 人工 | 累積策略心法 |
| 煞車 | **政治專討員** `/political` | 政治事件流 + 風險煞車 | 自動（bridge 預設關） | 觸發時擋新倉 |
| 結果 | **交易紀錄** `/trades` | 已成交訂單清單 | 自動 | 績效回饋 |

## 人只需要在兩個點出手

1. **策略知識庫晉升 curated**——validated 候選排好後，人看 OOS 數據按「晉升」（唯一強制人工閘）。
2. **跑真錢**——另受董事會核准頁 + 實盤雙閘（`ALPACA_BASE_URL` 實盤 + `ALLOW_LIVE_TRADING=true`）。

其餘（收料→產候選→OOS 驗證→排待審）全自動。**淘汰率高是健康的**：多數網路策略點子過不了
OOS 閘是預期結果，不是 bug。

## 排程與開關（`bot_manager.py` / `.env`，預設全關）

```
collector_scan (COLLECTOR_INTERVAL_MIN)   收料
   → discovery_bridge (DISCOVERY_HOUR=7)   探勘橋產候選   ← DISCOVERY_ENABLED
   → auto_validate (AUTO_VALIDATE_HOUR=8)  OOS 自動驗證   ← AUTO_VALIDATE_ENABLED
```

開啟步驟見 [`../guides/enable-auto-pipelines.md`](../guides/enable-auto-pipelines.md)；
管線體檢一鍵跑 `venv\Scripts\python.exe scripts\pipeline_smoke.py`。

## 品質地基（2026-06 修）

探勘橋產候選時，LLM 須**只用該策略合法的參數名**（schema 來自
`backend/strategies/__init__.py` 的 `STRATEGY_PARAM_SPECS`，prompt 會攤給模型、`triage_find`
會驗名 + 夾範圍）。修掉前 LLM 會亂猜名（如 `short_ma` vs 正解 `short_window`），錯名被策略
`params.get(..., 預設)` 靜默吃預設值，回測測到的不是提案策略 → 假淘汰。詳見
[`dev-pitfalls-log.md`](dev-pitfalls-log.md)。
