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

import { useState, useMemo, lazy, Suspense } from "react";
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
  ToggleButton,
  ToggleButtonGroup,
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
// 2x2 多視窗網格（同樣延遲載入，因為內含圖表庫）
const ChartGrid = lazy(() => import("./components/ChartGrid"));

// 畫面元件（每塊一個檔案）
import Header from "./components/Header";
import AccountCard from "./components/AccountCard";
import BotList from "./components/BotList";
import BacktestPanel from "./components/BacktestPanel";
import AutoBacktestPanel from "./components/AutoBacktestPanel";
import TradesTable from "./components/TradesTable";
import EditBotDialog from "./components/EditBotDialog";
import ConfirmDialog from "./components/ConfirmDialog";
import StrategyWorkbench from "./components/StrategyWorkbench";
import LiveQuote from "./components/LiveQuote";
import FundamentalsPanel from "./components/FundamentalsPanel";
import RecommendationsPanel from "./components/RecommendationsPanel";
import { buildBotPriceLines, findBotForSymbol } from "./utils/priceLines";

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

  // 圖表水位線：找出正在跑這檔股票的 Bot，算出進場/止損/追蹤止盈三條線。
  // 用 useMemo 快取，避免每次 render 都產生新陣列（否則圖表會一直重畫線）。
  const chartPriceLines = useMemo(
    () => buildBotPriceLines(findBotForSymbol(bots, chartSymbol)),
    [bots, chartSymbol]
  );

  // 目前分頁：0 = 儀表板，1 = K 線圖
  const [tab, setTab] = useState(0);

  // K 線圖佈局："single" = 單一大圖，"grid" = 2x2 四格同時盯
  const [chartView, setChartView] = useState("single");

  // 回測相關狀態
  const [btForm, setBtForm] = useState({
    strategy: "ma_crossover",
    symbol: "AAPL",
    days: 365,
    initial_cash: 10000,
  });
  const [btResult, setBtResult] = useState(null); // 回測結果
  const [btLoading, setBtLoading] = useState(false); // 是否回測中

  // 正在編輯的 Bot（null = 沒有打開編輯視窗）
  const [editBot, setEditBot] = useState(null);

  // 準備要刪除的 Bot（null = 沒有打開刪除確認視窗）
  const [deleteTarget, setDeleteTarget] = useState(null);

  // 一鍵部署：把 AI 推薦的策略直接變成一個啟用中的 Bot
  // （重用既有 createBot + startBot 流程，不另造邏輯）
  async function handleDeploy(rec) {
    setError("");
    setMessage("");
    try {
      const bot = await api.createBot({
        name: `AI-${rec.symbol}-${rec.strategy_key}`,
        strategy: rec.strategy_key,
        symbol: rec.symbol,
        params: rec.params || {},
        trade_amount: Number(rec.suggested_cash) || 1000,
      });
      // 建立後立刻掛排程，讓它真的開始監聽（全程 Paper）
      await api.startBot(bot.id);
      setMessage(`已部署 AI 推薦 Bot：${rec.symbol}（${rec.strategy_key}）`);
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
          sx={{
            flex: 1,
            minWidth: 0,
            py: 4,
            px: { xs: 2, md: 4 },
            // 進場輕輕浮現（index.css 定義的 keyframes，克制的高級感）
            animation: "albeeFadeUp .5s ease both",
          }}
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
          <Tab label="AI 探勘" />
          <Tab label="K 線圖" />
          <Tab label="基本面" />
        </Tabs>

        {/* ===== 儀表板分頁（純監控中心：上方總覽 + AI 燈號，下方服役中 Bot）===== */}
        {tab === 0 && (
          <Box>
            <AccountCard account={account} />
            {/* AI 市場燈號：不再手填表單建 Bot，改引導去「AI 探勘」一鍵部署 */}
            <Alert
              severity="info"
              sx={{ mb: 2 }}
              action={
                <Button color="inherit" size="small" onClick={() => setTab(1)}>
                  前往 AI 探勘
                </Button>
              }
            >
              想新增 Bot？讓 AI 盤前海選幫你挑高期望值（EV）策略，檢閱後一鍵部署。
            </Alert>
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
            {/* 全自動掃描最佳策略（一鍵最強）：放在手動回測上方當主打 */}
            <AutoBacktestPanel />
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

        {/* ===== AI 探勘分頁 ===== */}
        {tab === 1 && <RecommendationsPanel onDeploy={handleDeploy} />}

        {/* ===== K 線圖分頁 ===== */}
        {tab === 2 && (
          <Box>
            {/* 佈局切換：單一大圖 / 2x2 四格 */}
            <Box sx={{ mb: 2 }}>
              <ToggleButtonGroup
                size="small"
                exclusive
                value={chartView}
                onChange={(e, v) => v && setChartView(v)}
              >
                <ToggleButton value="single">單一</ToggleButton>
                <ToggleButton value="grid">2x2 四格</ToggleButton>
              </ToggleButtonGroup>
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
              {chartView === "grid" ? (
                // ----- 2x2 網格：每格自帶代號輸入與水位線 -----
                <ChartGrid bots={bots} />
              ) : (
                // ----- 單一大圖 -----
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
                  </Box>
                  {/* 即時報價（WebSocket 推送，價格會即時跳動、依漲跌變色） */}
                  <Box sx={{ mb: 2 }}>
                    <LiveQuote symbol={chartSymbol} />
                  </Box>
                  {/* 可拖拉調整大小的圖表容器（拉右下角） */}
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
                      priceLines={chartPriceLines}
                    />
                  </Box>
                  <Typography variant="caption" color="text.secondary">
                    提示：拖曳圖表框的右下角可調整高度。
                  </Typography>
                </Box>
              )}
            </Suspense>
          </Box>
        )}

        {/* ===== 基本面分頁 ===== */}
        {tab === 3 && <FundamentalsPanel />}
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
