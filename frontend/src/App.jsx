// ============================================================
// Albee Stock 主畫面（編排層）
// ============================================================
// 拆分後 App.jsx 只負責三件事：
//   1. 管所有「狀態」(useState)——資料、表單、分頁、訊息
//   2. 管所有「跟後端溝通的動作」(handleXxx)——呼叫 api.js
//   3. 把資料與動作「分配」給各個畫面元件 (components/)
//
// 實際長相（卡片、表格、彈窗）都搬到 components/ 底下，這裡只管邏輯。
// 想改某一塊的外觀，去對應的元件檔改；想改資料流，留在這裡改。

import { useState, useMemo, useEffect, lazy, Suspense } from "react";
import { api } from "./api";
import {
  Typography,
  Container,
  Box,
  TextField,
  Button,
  Alert,
  CssBaseline,
  Tabs,
  Tab,
  LinearProgress,
} from "@mui/material";
import { ThemeProvider } from "@mui/material/styles";
import { theme } from "./theme";
import { useDashboardData } from "./hooks/useDashboardData";

// 用 React.lazy 延遲載入 K 線圖元件：
//   一般 import 會把元件打包進主程式，一開啟網頁就下載。
//   lazy(() => import(...)) 改成「第一次真的要顯示它時」才另外去下載那一塊。
//   K 線圖在獨立分頁、不是一進來就看的東西，很適合這樣切出去。
//   注意：lazy 元件一定要包在 <Suspense> 裡，提供載入中的替代畫面。
const LightweightChart = lazy(() => import("./LightweightChart"));

// 畫面元件（每塊一個檔案）
import Header from "./components/Header";
import AccountCard from "./components/AccountCard";
import CreateBotForm from "./components/CreateBotForm";
import BotList from "./components/BotList";
import BacktestPanel from "./components/BacktestPanel";
import TradesTable from "./components/TradesTable";
import EditBotDialog from "./components/EditBotDialog";
import ConfirmDialog from "./components/ConfirmDialog";
import StrategyWorkbench from "./components/StrategyWorkbench";
import LiveQuote from "./components/LiveQuote";
import FundamentalsPanel from "./components/FundamentalsPanel";

// 風控欄位用：使用者在畫面填「百分比整數」（例如 10 代表 10%），
// 但後端存的是小數（0.10）。下面兩個小工具負責互轉，空白 = null（不啟用該機制）。
function pctToDecimal(v) {
  if (v === "" || v === null || v === undefined) return null;
  const n = Number(v);
  return Number.isFinite(n) ? n / 100 : null;
}
function decimalToPct(v) {
  if (v === null || v === undefined || v === "") return "";
  // 用 toFixed 收掉浮點誤差（0.03*100 = 3.0000000004），再轉回數字去尾零
  return Number((Number(v) * 100).toFixed(4));
}

function App() {
  // 儀表板資料（account/status/bots/trades）與「重新載入」都交給自訂 Hook 管理。
  // App 不必再自己寫一堆 useState 與 loadAll，畫面邏輯更乾淨。
  const { account, status, bots, trades, loading, loadError, reload } =
    useDashboardData();

  // 這兩個是「操作」產生的訊息（建立/刪除/啟停 Bot 的結果），跟資料載入分開管理。
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  // 圖表目前顯示的股票（chartSymbol）與輸入框的暫存值（symbolInput）
  const [chartSymbol, setChartSymbol] = useState("AAPL");
  const [symbolInput, setSymbolInput] = useState("AAPL");

  // 目前分頁：0 = 儀表板，1 = K 線圖
  const [tab, setTab] = useState(0);

  // 圖表檢視模式："single" 單檔大圖 / "grid" 2×2 多檔同時看
  const [chartView, setChartView] = useState("single");

  // 各股票的 Alpaca 持倉（含進場均價），以代號為 key。空手時該檔不存在或 avg_entry_price 為 null。
  // 用 map 而非單一值，是為了「網格模式」能同時拿多檔的進場均價畫線。
  const [positionsBySymbol, setPositionsBySymbol] = useState({});

  // 網格要顯示哪幾檔：優先用「啟用中 Bot 盯的股票」（去重、最多 4 檔湊 2×2）；
  // 都沒有啟用中的 Bot 時，退回目前單檔的 chartSymbol。
  const gridSymbols = useMemo(() => {
    const actives = [...new Set(bots.filter((b) => b.is_active).map((b) => b.symbol))];
    return (actives.length ? actives : [chartSymbol]).slice(0, 4);
  }, [bots, chartSymbol]);

  // 目前畫面上實際顯示的股票清單（單檔模式只有 chartSymbol；網格模式是 gridSymbols）
  const displayedSymbols = chartView === "grid" ? gridSymbols : [chartSymbol];
  // 把清單接成穩定字串當 effect 依賴，避免每次 render 都重抓
  const displayedKey = displayedSymbols.join(",");

  // 顯示中的股票，各去後端查一次持倉進場均價。
  // 查不到（空手／沒連線）就當沒有，不影響其他水位線。
  useEffect(() => {
    let cancelled = false;
    Promise.all(
      displayedSymbols.map((sym) =>
        api
          .getPosition(sym)
          .then((p) => [sym, p])
          .catch(() => [sym, null])
      )
    ).then((pairs) => {
      if (!cancelled) setPositionsBySymbol(Object.fromEntries(pairs));
    });
    return () => {
      cancelled = true;
    };
    // displayedKey 已涵蓋 displayedSymbols 內容變化
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [displayedKey]);

  // 把某檔股票的 Bot 風控狀態算成圖表水位線：
  //   進場均價（灰虛線）   ← 來自 Alpaca 持倉
  //   固定止損（紅實線）   = 進場均價 ×(1 − stop_loss_pct)
  //   固定止盈（藍實線）   = 進場均價 ×(1 + take_profit_pct)
  //   追蹤止損（綠實線）   = peak_price ×(1 − trailing_stop_pct)，純前端可算
  const buildPriceLines = (symbol) => {
    const lines = [];
    const entry = positionsBySymbol[symbol]?.avg_entry_price ?? null;

    // 進場均價線（整檔股票一條就好，不分 Bot）
    if (entry != null) {
      lines.push({ price: entry, color: "#9aa0a6", lineStyle: 2, title: "進場均價" });
    }

    bots
      .filter((b) => b.symbol === symbol && b.is_active)
      .forEach((b) => {
        if (entry != null && b.stop_loss_pct != null) {
          lines.push({
            price: entry * (1 - b.stop_loss_pct),
            color: "#ef5350", // 紅＝止損
            lineStyle: 0,
            title: `止損 ${b.name}`,
          });
        }
        if (entry != null && b.take_profit_pct != null) {
          lines.push({
            price: entry * (1 + b.take_profit_pct),
            color: "#42a5f5", // 藍＝止盈
            lineStyle: 0,
            title: `止盈 ${b.name}`,
          });
        }
        // 追蹤止損不依賴進場均價，只要有持倉最高價＋追蹤比例就畫得出來
        if (b.peak_price != null && b.trailing_stop_pct != null) {
          lines.push({
            price: b.peak_price * (1 - b.trailing_stop_pct),
            color: "#26a69a", // 青綠＝保護獲利的追蹤止損
            lineStyle: 0,
            title: `追蹤止損 ${b.name}`,
          });
        }
      });
    return lines;
  };

  // 回測相關狀態
  const [btForm, setBtForm] = useState({
    strategy: "ma_crossover",
    symbol: "AAPL",
    days: 365,
    initial_cash: 10000,
  });
  const [btResult, setBtResult] = useState(null); // 回測結果
  const [btLoading, setBtLoading] = useState(false); // 是否回測中

  const [form, setForm] = useState({
    name: "",
    strategy: "ma_crossover",
    symbol: "",
    trade_amount: 1000,
    // 風控欄位（填百分比整數，空白 = 不啟用）；interval 為監測頻率（秒）
    tp: "",
    sl: "",
    trail: "",
    interval: 60,
  });

  // 正在編輯的 Bot（null = 沒有打開編輯視窗）
  const [editBot, setEditBot] = useState(null);

  // 準備要刪除的 Bot（null = 沒有打開刪除確認視窗）
  const [deleteTarget, setDeleteTarget] = useState(null);

  // 送出建立 Bot
  async function handleCreate(e) {
    e.preventDefault();
    setError("");
    setMessage("");
    try {
      await api.createBot({
        name: form.name,
        strategy: form.strategy,
        symbol: form.symbol.toUpperCase(),
        params: {},
        trade_amount: Number(form.trade_amount),
        take_profit_pct: pctToDecimal(form.tp),
        stop_loss_pct: pctToDecimal(form.sl),
        trailing_stop_pct: pctToDecimal(form.trail),
        check_interval_sec: Number(form.interval) || 60,
      });
      setMessage(`已建立 Bot：${form.name}`);
      setForm({ ...form, name: "", symbol: "" });
      reload();
    } catch (e) {
      setError(e.message);
    }
  }

  // 手動執行某個 Bot
  async function handleRun(id) {
    setError("");
    setMessage("");
    try {
      const r = await api.runBot(id);
      setMessage(`${r.message}（買賣訊號請看後端終端機的 log）`);
      reload();
    } catch (e) {
      setError(e.message);
    }
  }

  // 執行回測
  async function handleBacktest() {
    setError("");
    setBtResult(null);
    setBtLoading(true); // 開始載入（按鈕會變「回測中…」）
    try {
      const r = await api.runBacktest({
        strategy: btForm.strategy,
        symbol: btForm.symbol.toUpperCase(),
        params: {},
        days: Number(btForm.days),
        initial_cash: Number(btForm.initial_cash),
      });
      setBtResult(r);
    } catch (e) {
      setError(e.message);
    } finally {
      setBtLoading(false); // 不論成功失敗都結束載入
    }
  }

  // 啟動 / 停止 Bot（依目前狀態切換）
  async function handleToggleActive(bot) {
    setError("");
    setMessage("");
    try {
      if (bot.is_active) {
        await api.stopBot(bot.id);
        setMessage(`已停止 Bot：${bot.name}`);
      } else {
        await api.startBot(bot.id);
        setMessage(
          `已啟動 Bot：${bot.name}（每 ${bot.check_interval_sec || 60} 秒檢查一次）`
        );
      }
      reload();
    } catch (e) {
      setError(e.message);
    }
  }

  // 真正執行刪除（由確認視窗的「確認」鈕觸發）
  async function confirmDelete() {
    const bot = deleteTarget;
    setDeleteTarget(null); // 先關視窗
    setError("");
    setMessage("");
    try {
      await api.deleteBot(bot.id);
      setMessage(`已刪除 Bot：${bot.name}`);
      reload();
    } catch (e) {
      setError(e.message);
    }
  }

  // 儲存編輯（送出 PUT）
  async function handleEditSave() {
    setError("");
    setMessage("");
    try {
      await api.updateBot(editBot.id, {
        name: editBot.name,
        strategy: editBot.strategy,
        symbol: editBot.symbol.toUpperCase(),
        params: {},
        trade_amount: Number(editBot.trade_amount),
        take_profit_pct: pctToDecimal(editBot.tp),
        stop_loss_pct: pctToDecimal(editBot.sl),
        trailing_stop_pct: pctToDecimal(editBot.trail),
        check_interval_sec: Number(editBot.interval) || 60,
      });
      setMessage(`已更新 Bot：${editBot.name}`);
      setEditBot(null); // 關閉視窗
      reload();
    } catch (e) {
      setError(e.message);
    }
  }

  return (
    <ThemeProvider theme={theme}>
      {/* CssBaseline：統一各瀏覽器的預設樣式 */}
      <CssBaseline />

      {/* 頂部標題列（右側顯示模擬／實盤標示） */}
      <Header status={status} />

      {/* 實盤警告橫幅：雙閘全開時才出現，提醒此刻下單會動真錢 */}
      {status?.live_armed && (
        <Alert severity="error" square sx={{ borderRadius: 0 }}>
          ⚠️ 目前是<strong>實盤模式</strong>，所有下單將動用<strong>真實資金</strong>。請務必確認。
        </Alert>
      )}

      {/* 載入中時，在標題列下方顯示一條細進度條（抓資料時才出現） */}
      {loading && <LinearProgress />}

      {/* 主內容（左）＋ 策略工作台（右）橫向並排 */}
      <Box sx={{ display: "flex", alignItems: "flex-start" }}>
        <Container
          maxWidth={false}
          sx={{ flex: 1, minWidth: 0, py: 4, px: { xs: 2, md: 4 } }}
        >
        {/* 訊息提示：操作錯誤(error) 與 資料載入錯誤(loadError) 都顯示出來 */}
        {(error || loadError) && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error || loadError}
          </Alert>
        )}
        {message && (
          <Alert severity="success" sx={{ mb: 2 }}>
            {message}
          </Alert>
        )}

        {/* 分頁切換 */}
        <Tabs value={tab} onChange={(e, v) => setTab(v)} sx={{ mb: 3 }}>
          <Tab label="儀表板" />
          <Tab label="K 線圖" />
          <Tab label="基本面" />
        </Tabs>

        {/* ===== 儀表板分頁 ===== */}
        {tab === 0 && (
          <Box>
            <AccountCard account={account} />
            <CreateBotForm form={form} setForm={setForm} onSubmit={handleCreate} />
            <BotList
              bots={bots}
              onToggle={handleToggleActive}
              onRun={handleRun}
              onEdit={(b) =>
                setEditBot({
                  ...b,
                  // 後端存小數，編輯框顯示百分比整數
                  tp: decimalToPct(b.take_profit_pct),
                  sl: decimalToPct(b.stop_loss_pct),
                  trail: decimalToPct(b.trailing_stop_pct),
                  interval: b.check_interval_sec ?? 60,
                })
              }
              onDelete={setDeleteTarget}
            />
            <BacktestPanel
              btForm={btForm}
              setBtForm={setBtForm}
              btResult={btResult}
              btLoading={btLoading}
              onRun={handleBacktest}
            />
            <TradesTable trades={trades} />
          </Box>
        )}

        {/* ===== K 線圖分頁 ===== */}
        {tab === 1 && (
          <Box>
            <Box sx={{ display: "flex", gap: 1, mb: 2 }}>
              <TextField
                size="small"
                label="股票代號"
                value={symbolInput}
                onChange={(e) => setSymbolInput(e.target.value)}
                placeholder="例如：AAPL、TSLA、NVDA"
              />
              <Button
                variant="contained"
                onClick={() => setChartSymbol(symbolInput.toUpperCase())}
              >
                載入圖表
              </Button>
              {/* 單檔 / 2×2 網格 檢視切換 */}
              <Box sx={{ flexGrow: 1 }} />
              <Button
                variant={chartView === "single" ? "contained" : "outlined"}
                onClick={() => setChartView("single")}
              >
                單檔
              </Button>
              <Button
                variant={chartView === "grid" ? "contained" : "outlined"}
                onClick={() => setChartView("grid")}
              >
                2×2 網格
              </Button>
            </Box>

            {/* Suspense：lazy 圖表元件還在下載時，先顯示 fallback 提示 */}
            <Suspense
              fallback={
                <Box
                  sx={{
                    height: "75vh",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    color: "text.secondary",
                  }}
                >
                  圖表載入中…
                </Box>
              }
            >
              {chartView === "single" ? (
                // ===== 單檔模式：即時報價 + 一張可拉高的大圖 =====
                <>
                  {/* 即時報價（WebSocket 推送，價格會即時跳動、依漲跌變色） */}
                  <Box sx={{ mb: 2 }}>
                    <LiveQuote symbol={chartSymbol} />
                  </Box>
                  <Box
                    sx={{
                      resize: "vertical",
                      overflow: "hidden",
                      height: "75vh",
                      minHeight: 320,
                      border: "1px solid",
                      borderColor: "divider",
                      borderRadius: 1,
                    }}
                  >
                    <LightweightChart
                      symbol={chartSymbol}
                      height="100%"
                      source="yfinance"
                      priceLines={buildPriceLines(chartSymbol)}
                    />
                  </Box>
                  <Typography variant="caption" color="text.secondary">
                    提示：拖曳圖表框的右下角可調整高度。
                  </Typography>
                </>
              ) : (
                // ===== 網格模式：2×2 同時監控多檔（啟用中 Bot 的標的）=====
                <Box
                  sx={{
                    display: "grid",
                    gridTemplateColumns: "1fr 1fr",
                    gap: 1,
                    height: "78vh",
                  }}
                >
                  {gridSymbols.map((sym) => (
                    <Box
                      key={sym}
                      sx={{
                        border: "1px solid",
                        borderColor: "divider",
                        borderRadius: 1,
                        overflow: "hidden",
                        display: "flex",
                        flexDirection: "column",
                        minHeight: 0, // 讓 grid 子項能正確收縮，圖表才不會撐爆
                      }}
                    >
                      <Typography
                        variant="caption"
                        sx={{ px: 1, py: 0.5, fontWeight: 600 }}
                      >
                        {sym}
                      </Typography>
                      <Box sx={{ flexGrow: 1, minHeight: 0 }}>
                        <LightweightChart
                          symbol={sym}
                          height="100%"
                          source="yfinance"
                          priceLines={buildPriceLines(sym)}
                        />
                      </Box>
                    </Box>
                  ))}
                </Box>
              )}
            </Suspense>
          </Box>
        )}

        {/* ===== 基本面分頁 ===== */}
        {tab === 2 && <FundamentalsPanel />}
        </Container>

        {/* 右側策略工作台（自管資料流，可收合／橫向拉寬） */}
        <StrategyWorkbench />
      </Box>

      {/* 編輯 Bot 的彈出視窗 */}
      <EditBotDialog
        editBot={editBot}
        setEditBot={setEditBot}
        onSave={handleEditSave}
      />

      {/* 刪除 Bot 的確認視窗（取代原本的 window.confirm） */}
      <ConfirmDialog
        open={!!deleteTarget}
        title="刪除 Bot"
        message={
          deleteTarget
            ? `確定要刪除「${deleteTarget.name}」嗎？此動作無法復原。`
            : ""
        }
        confirmText="刪除"
        onConfirm={confirmDelete}
        onClose={() => setDeleteTarget(null)}
      />
    </ThemeProvider>
  );
}

export default App;
