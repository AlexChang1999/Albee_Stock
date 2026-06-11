# Albee_Stock 交易系統工作流圖

> 用 [Mermaid](https://mermaid.js.org/) 畫（圖即程式碼，進 git）。
> **看圖方式**：推上 GitHub 自動渲染，或 VSCode 裝「Markdown Preview Mermaid Support」擴充後預覽。
>
> 共 5 張圖：
> 1. [高層全景](#圖-1高層全景) — 三大子系統一張看懂
> 2. [即時/自動交易決策流水線](#圖-2即時自動交易決策流水線flow-a) — Bot 每輪怎麼決策下單
> 3. [回測 / EV 流水線](#圖-3回測--ev-流水線flow-b) — 怎麼挑出冠軍策略
> 4. [Phase 7 層驗證流](#圖-4phase-7-層驗證流flow-c) — 每層加分到底值不值得留
> 5. [Phase 8–11 知識庫 → AI 公司軌](#圖-5phase-811-知識庫--ai-公司軌flow-d) — 素材進料、知識庫晉升、戰情監控、維運安全
>
> 圖內容已對照 `backend/` 實際程式碼流程，非憑記憶。

---

## 圖 1：高層全景

整個系統三條軌 + 共用底座。研究軌挑策略 → 實盤軌執行 → 驗證軌檢查各層是否真的加分。

```mermaid
flowchart TB
    subgraph DATA["共用底座"]
        MD["market_data.get_bars<br/>(Alpaca / yfinance)"]
        BE["backtest_engine._run_on_df<br/>(含成本 + 隔日成交)"]
        DB[("SQLite<br/>Bot / Trade / DecisionLog<br/>Preset / BacktestRun")]
    end

    subgraph RESEARCH["① 研究 / 回測軌"]
        WL["watchlist 觀察清單"] --> SC["screener.screen_watchlist<br/>量能 → 情緒 → EV 掃描"]
        SC --> OPT["optimizer.run_auto_backtest<br/>OOS EV 排名挑冠軍"]
        OPT --> PRE["presets 策略方案<br/>(依 EV 排序歷史)"]
    end

    subgraph LIVE["② 實盤 / 自動軌"]
        SCH["APScheduler 排程"] --> BM["bot_manager.run_bot_once"]
        BM --> PIPE["決策流水線<br/>(見圖 2)"]
        PIPE --> ORD["alpaca_client.submit_market_order<br/>雙閘安全閥"]
        ORD --> NT["notifier 通知<br/>(LINE / Discord)"]
    end

    subgraph VALID["③ 驗證軌"]
        LV["layer_validation.validate_layers"] --> WF["validation.walk_forward_splits<br/>walk-forward / purged k-fold"]
        WF --> VERD["各層 worth 判決<br/>(見圖 4)"]
    end

    MD --- RESEARCH
    MD --- LIVE
    MD --- VALID
    BE --- RESEARCH
    BE --- VALID
    PRE -.冠軍策略.-> BM
    PIPE --> DB
    OPT --> DB
    VERD -.決定各層去留.-> LIVE

    classDef base fill:#1a2332,stroke:#4a90d9,color:#cde
    classDef research fill:#1a2e1a,stroke:#5cb85c,color:#cec
    classDef live fill:#2e1a1a,stroke:#d9534f,color:#ecc
    classDef valid fill:#2e2a1a,stroke:#f0ad4e,color:#eec
    class MD,BE,DB base
    class WL,SC,OPT,PRE research
    class SCH,BM,PIPE,ORD,NT live
    class LV,WF,VERD valid
```

---

## 圖 2：即時/自動交易決策流水線（Flow A）

`bot_manager.run_bot_once(bot_id)` 每輪實際順序。紅色 = SKIP 出口（不下單）。
標籤 `[P6-xx]` / `[P7-xx]` = Phase 6 / Phase 7 第幾步。

> ⚠️ **Kelly 部位（P7-04）與事件風險閘（P7-06）只在 `automation.run_auto_deploy` 自動部署流**，
> **不在**手動 Bot 流。圖中以虛線框標出。

```mermaid
flowchart TD
    START["run_bot_once(bot_id)<br/>重查最新 bot 設定 [P6-06]"] --> MO{"is_market_open?"}
    MO -- 否 --> SKIP_MO["SKIP：休市"]:::skip
    MO -- 是 --> POS["get_position / get_latest_price"]
    POS --> HOLD{"持有部位?"}

    HOLD -- 是 --> EXIT["risk_manager.check_exit<br/>止損 / 追蹤止損 / 止盈"]
    EXIT --> EXITQ{"觸發出場?"}
    EXITQ -- 是 --> SELL["submit_market_order 賣出"] --> REC
    EXITQ -- 否 --> HOLDDONE["維持持有<br/>_persist_peak 更新最高價"]:::skip

    HOLD -- 否 --> ADAPT{"adaptive bot?"}

    ADAPT -- 否 --> FIX["lookback.required_lookback_days<br/>→ market_data.get_bars<br/>→ strategies/*.generate_signal"]
    ADAPT -- 是 --> AD1["regime_features.compute_features [P7-01]"]
    AD1 --> AD2["regime.classify_regime [P7-02]"]
    AD2 --> AD3["strategy_selector.select_strategy [P7-03]"]
    AD3 --> AD4["選中策略.generate_signal"]
    AD4 --> AD5["meta_label.should_take [P7-05]<br/>信心不足 → 降為 HOLD"]

    FIX --> SIG{"訊號 = BUY?"}
    AD5 --> SIG
    SIG -- HOLD/SELL --> NOOP["不進場<br/>_record_decision 觀望"]:::skip

    SIG -- BUY --> CB["circuit_breaker.check_breaker [P6-09]<br/>組合回撤熔斷"]
    CB --> CBQ{"熔斷觸發?"}
    CBQ -- 是 --> SKIP_CB["SKIP：ACTION_SKIPPED_CIRCUIT_BREAKER"]:::skip
    CBQ -- 否 --> QTY["算 qty = trade_amount / price"]
    QTY --> BP["_available_buying_power [P6-05]"]
    BP --> BPQ{"購買力足?"}
    BPQ -- 否 --> SKIP_BP["SKIP：ACTION_SKIPPED_NO_BUYING_POWER"]:::skip
    BPQ -- 是 --> AUTO

    subgraph AUTO_BOX ["僅 automation.run_auto_deploy 自動部署流"]
        AUTO["sizing.kelly_trade_amount [P7-04]<br/>分數凱利部位"] --> EVT["event_risk.assess_event_risk [P7-06]<br/>事件風險煞車"]
    end

    AUTO_BOX --> SUBMIT["submit_market_order<br/>雙閘安全閥：IS_PAPER / ALLOW_LIVE_TRADING [P6 鐵則]"]
    SUBMIT --> REC["_record_and_notify<br/>TradeLog + notifier"]
    REC --> DL["_record_decision (DecisionLog) [P6-08]"]
    DL --> PEAK["_persist_peak → _mark_checked"]

    classDef skip fill:#3a1a1a,stroke:#d9534f,color:#fcc
```

---

## 圖 3：回測 / EV 流水線（Flow B）

`screener.screen_watchlist` → `optimizer.run_auto_backtest`：三層篩出冠軍策略，
**一律看樣本外（OOS）EV** 排名，不在整段歷史挑樣本內最佳（防過擬合）。

```mermaid
flowchart TD
    WL["watchlist"] --> L1["Layer 1 量能<br/>_layer1_volume<br/>volume_ratio ≥ 門檻，取 top N"]
    L1 --> L2["Layer 2 情緒 (best-effort)<br/>_layer2_sentiment<br/>llm.complete → parse_sentiment"]
    L2 --> L3["Layer 3 EV 掃描<br/>optimizer.run_auto_backtest"]

    L3 --> SPLIT["split_train_test [P6-04]<br/>OOS 70% 訓練 / 30% 測試"]
    SPLIT --> LOOP["每策略 × 每參數組"]
    LOOP --> RUN["backtest_engine._run_on_df<br/>• 隔日開盤成交 [P6-03]<br/>• 含手續費 + 滑價 [P6-02]"]
    RUN --> METRIC["算 EV / 勝率 / avg_win / avg_loss<br/>/ max_drawdown / round_trips"]
    METRIC --> RANK["以 **OOS expected_value** 排名"]
    RANK --> BEST["挑冠軍策略 + 參數"]

    BEST --> GATE["screen_watchlist 最終排序 [P6-07]<br/>(OOS_EV 主序, 情緒 次序)<br/>OOS_EV > 門檻才留"]
    GATE --> RECO["recommendations<br/>{symbol, strategy, params, OOS metrics, sentiment}"]
    RECO -.-> AUTODEPLOY["automation 自動部署<br/>(接圖 2 的下單)"]

    classDef hl fill:#1a2e1a,stroke:#5cb85c,color:#cec
    class RANK,BEST,GATE hl
```

---

## 圖 4：Phase 7 層驗證流（Flow C）

`layer_validation.validate_layers`：用 walk-forward 切 folds，每層拿 **baseline vs candidate**
都跑 `_run_on_df`，比 OOS 改善是否過門檻。誠實判決「這層加分到底值不值得留」。

```mermaid
flowchart TD
    START["validate_layers(watchlist)<br/>market_data.get_bars 整年資料"] --> SPLIT["validation.walk_forward_splits<br/>產 folds (共用)"]

    SPLIT --> META["validate_meta_layer [P7-05]<br/>base vs MetaFilteredStrategy"]
    SPLIT --> ADAPT["validate_adaptive_layer [P7-03]<br/>best_fixed vs AdaptiveMappedStrategy"]
    SPLIT --> KELLY["validate_kelly_layer [P7-04]<br/>固定 f vs 凱利 f (terminal_return)"]
    SPLIT --> EVENT["event 事件風險閘 [P7-06]"]

    META --> JM["is_layer_worth_it<br/>folds≥min 且 改善≥門檻"]
    ADAPT --> JA["is_layer_worth_it"]
    KELLY --> JK["is_layer_worth_it"]

    JM --> RM["✅ 實測：過 (留)"]:::pass
    JA --> RA["❌ 實測：沒過 (該砍)"]:::fail
    JK --> RK["❌ 實測：沒過 (該砍)"]:::fail
    EVENT --> RE["⚪ 不可驗證<br/>無時點情緒史, worth=None<br/>(只煞車不猜方向, 保留)"]:::na

    RM --> REPORT["validate_layers.py 報表<br/>layer | worth | folds | improvement | reason"]
    RA --> REPORT
    RK --> REPORT
    RE --> REPORT

    classDef pass fill:#1a2e1a,stroke:#5cb85c,color:#cec
    classDef fail fill:#3a1a1a,stroke:#d9534f,color:#fcc
    classDef na fill:#23262e,stroke:#888,color:#ccc
```

---

## 圖 5：Phase 8–11 知識庫 → AI 公司軌（Flow D）

Phase 8（策略知識庫 + 人在迴路晉升）、Phase 10（AI 公司編排）、Phase 11（總經資料地基）
與 backlog H（維運安全軌）怎麼接在一起。**人工關卡只有兩個**：知識庫晉升、董事會核准。

```mermaid
flowchart TD
    subgraph FEED["進料（Phase 10/11）"]
        COL["collector RSS 蒐集員<br/>(預設關) → raw_strategy_find"]
        POL["political Discord 政治員<br/>(煞車, bridge 預設關)"]
        MAC["fred_client / macro_data<br/>FRED 總經序列 [P11]"]
        OFP["orderflow_proxy 籌碼面 proxy [P11]"]
    end

    subgraph KNOW["策略知識庫（Phase 8）"]
        GEN["strategy_generator.propose_params<br/>LLM 提案參數 → candidate"]
        VAL["evolution.validate_candidate<br/>walk-forward OOS 驗證"]
        PROM{"人工晉升<br/>validated → curated"}
    end

    subgraph COMPANY["AI 公司（Phase 10）"]
        SCAN["opportunity_scan 常駐探勘<br/>→ Opportunity (OOS 指標)"]
        FAC["factor_snapshot 因子報表"]
        OVR["company.overview 戰情頁聚合"]
        BOARD{"董事會核准<br/>promotion: proposed_live → approved_live"}
    end

    subgraph OPS["維運安全軌（backlog H）"]
        PROT["protective_orders + alpaca_client<br/>券商端 GTC 保護單 [H1]"]
        HB["heartbeat 日報 + dead-man ping [H2]"]
        TRK["tracking error 對帳<br/>連 3 違規自動停 Bot [H3]"]
    end

    COL -.靈感素材.-> GEN
    GEN --> VAL --> PROM
    PROM -- curated --> DEPLOY["automation.run_auto_deploy<br/>(模式 B, OOS 門檻 + 名額)"]
    SCAN --> OVR
    FAC --> OVR
    POL -.風險煞車.-> DEPLOY
    MAC -.特徵.-> SCAN
    OFP -.特徵.-> SCAN
    DEPLOY --> BOT["Bot 實跑 (圖 2 流水線)"]
    BOT --> PROT
    BOT --> TRK
    BOT --> HB
    BOT -. 達標證據 .-> BOARD
    BOARD -- 核准旗標 --> LIVE["真錢（仍須雙閘安全閥）"]

    classDef human fill:#2e2a1a,stroke:#f0ad4e,color:#eec
    class PROM,BOARD human
```

---

## 對照表：圖 ↔ 程式碼

| 圖 | 入口函式 | 關鍵模組 |
|----|----------|----------|
| 圖 2 實盤 | `bot_manager.run_bot_once` | `regime_features` / `regime` / `strategy_selector` / `meta_label` / `circuit_breaker` / `capital` / `risk_manager` / `alpaca_client` |
| 圖 3 回測 | `screener.screen_watchlist` → `optimizer.run_auto_backtest` | `backtest_engine._run_on_df` / `optimizer.split_train_test` |
| 圖 4 驗證 | `scripts/validate_layers.py` → `layer_validation.validate_layers` | `validation.walk_forward_splits` / `validation.is_layer_worth_it` |
| 圖 5 知識庫/公司 | `routers/knowledge.py` / `routers/company.py` | `strategy_generator` / `evolution` / `opportunity_scan` / `collector` / `political` / `heartbeat` / `tracking` / `protective_orders` |

> 圖會跟程式碼演進而過期。改動 `backend/` 流程順序時，記得同步本檔。
