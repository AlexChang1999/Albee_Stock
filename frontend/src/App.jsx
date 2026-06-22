// ============================================================
// Albee Stock 主畫面（編排層）
// ============================================================
// 拆分後 App.jsx 只負責三件事：
//   1. 管所有「狀態」(useState)——資料、表單、訊息
//   2. 管所有「跟後端溝通的動作」(handleXxx)——呼叫 api.js
//   3. 把資料與動作經 react-router 的 <Outlet context> 分配給各路由頁
//
// Phase 9 step-01：導覽從「上方 4 個 Tabs」重構成「左側 sidebar + 路由多頁」。
//   外殼在 components/SidebarLayout.jsx，各頁在 pages/。狀態與動作仍集中在這裡，
//   行為與原本一致（只是改用路由切換、儀表板瘦身）。

import { useState, useMemo, useEffect } from "react";
import { api } from "./api";
import { CssBaseline } from "@mui/material";
import { ThemeProvider } from "@mui/material/styles";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { buildTheme } from "./theme";
import { useDashboardData } from "./hooks/useDashboardData";

// 外殼 + 路由頁
import SidebarLayout from "./components/SidebarLayout";
import DashboardPage from "./pages/DashboardPage";
import AiExplorePage from "./pages/AiExplorePage";
import ChartsPage from "./pages/ChartsPage";
import FundamentalsPage from "./pages/FundamentalsPage";
import BacktestToolsPage from "./pages/BacktestToolsPage";
import TradesPage from "./pages/TradesPage";
import BacktestRunsPage from "./pages/BacktestRunsPage";
import PresetsPage from "./pages/PresetsPage";
import ExplorationsPage from "./pages/ExplorationsPage";
import DecisionsPage from "./pages/DecisionsPage";
import LibraryPage from "./pages/LibraryPage";
import EvolutionPage from "./pages/EvolutionPage";
import CompanyPage from "./pages/CompanyPage";
import PromotionPage from "./pages/PromotionPage";
import FactorsPage from "./pages/FactorsPage";
import CollectorPage from "./pages/CollectorPage";
import PoliticalPage from "./pages/PoliticalPage";
import BotReviewPage from "./pages/BotReviewPage";

// 常駐元件（外殼與彈窗）
import EditBotDialog from "./components/EditBotDialog";
import ConfirmDialog from "./components/ConfirmDialog";
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
  const { account, status, bots, trades, loading, loadError, reload } =
    useDashboardData();

  // 操作訊息（建立/刪除/啟停 Bot 的結果），跟資料載入分開管理。
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  // 亮/暗模式（E1）：記在 localStorage，下次開啟沿用；預設深藍。
  const [colorMode, setColorMode] = useState(
    () => localStorage.getItem("albee-color-mode") || "dark"
  );
  const muiTheme = useMemo(() => buildTheme(colorMode), [colorMode]);
  useEffect(() => {
    // index.css 用 body[data-mode] 切整套 CSS 變數（頁面底色、髮絲線…）
    document.body.dataset.mode = colorMode;
    localStorage.setItem("albee-color-mode", colorMode);
  }, [colorMode]);
  const toggleColorMode = () =>
    setColorMode((m) => (m === "dark" ? "light" : "dark"));

  // 圖表目前顯示的股票（chartSymbol）與輸入框的暫存值（symbolInput）
  const [chartSymbol, setChartSymbol] = useState("AAPL");
  const [symbolInput, setSymbolInput] = useState("AAPL");

  // 圖表水位線：找出正在跑這檔股票的 Bot，算出進場/止損/追蹤止盈三條線。
  const chartPriceLines = useMemo(
    () => buildBotPriceLines(findBotForSymbol(bots, chartSymbol)),
    [bots, chartSymbol]
  );

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
  // 準備要停止的 Bot（停止 = 危險動作，尤其實盤；與刪除一樣走二次確認）
  const [stopTarget, setStopTarget] = useState(null);

  // 一鍵部署：把 AI 推薦的策略直接變成一個啟用中的 Bot
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

  // 圖表上拖曳止損 / 追蹤止盈水位線 → 換算成的百分比存回後端
  async function handlePriceLineDrag(botId, field, pct) {
    setError("");
    setMessage("");
    try {
      await api.updateBotRisk(botId, { [field]: pct });
      const label = field === "stop_loss_pct" ? "止損" : "追蹤止盈";
      setMessage(`已更新${label}為 ${(pct * 100).toFixed(2)}%`);
      reload(); // 重抓 Bot，水位線回到最新資料
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
  // 啟動：直接做（無風險）。停止：危險動作 → 先開確認視窗，由 confirmStop 真正執行。
  async function handleToggleActive(bot) {
    setError("");
    setMessage("");
    if (bot.is_active) {
      setStopTarget(bot); // 開「停止 Bot」確認視窗
      return;
    }
    try {
      await api.startBot(bot.id);
      setMessage(
        `已啟動 Bot：${bot.name}（每 ${bot.check_interval_sec || 60} 秒檢查一次）`
      );
      reload();
    } catch (e) {
      setError(e.message);
    }
  }

  // 真正執行停止（由停止確認視窗的「停止」鈕觸發）
  async function confirmStop() {
    const bot = stopTarget;
    setStopTarget(null);
    setError("");
    setMessage("");
    try {
      await api.stopBot(bot.id);
      setMessage(`已停止 Bot：${bot.name}`);
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

  // 打開編輯視窗：後端存小數，編輯框顯示百分比整數
  function openEdit(b) {
    setEditBot({
      ...b,
      tp: decimalToPct(b.take_profit_pct),
      sl: decimalToPct(b.stop_loss_pct),
      trail: decimalToPct(b.trailing_stop_pct),
      interval: b.check_interval_sec ?? 60,
    });
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

  // 傳給各路由頁的共享資料/動作（頁面用 useOutletContext() 取）
  const outletContext = {
    // 資料
    account,
    status, // 交易環境（含 live_armed，給 AI 探勘頁的實盤部署確認用）
    bots,
    trades,
    loading, // 載入中（給各頁畫 Skeleton 載入態，E3）
    reload, // 讓子頁（如自動化試跑後）能要求重抓 account/bots/trades
    // Bot 動作
    onToggleActive: handleToggleActive,
    onRun: handleRun,
    onEdit: openEdit,
    onDelete: setDeleteTarget,
    onDeploy: handleDeploy,
    // 圖表
    chartView,
    setChartView,
    symbolInput,
    setSymbolInput,
    chartSymbol,
    setChartSymbol,
    chartPriceLines,
    onPriceLineDrag: handlePriceLineDrag,
    // 回測
    btForm,
    setBtForm,
    btResult,
    btLoading,
    onBacktest: handleBacktest,
  };

  return (
    <ThemeProvider theme={muiTheme}>
      {/* CssBaseline：統一各瀏覽器的預設樣式 */}
      <CssBaseline />

      <BrowserRouter>
        <Routes>
          <Route
            element={
              <SidebarLayout
                status={status}
                loading={loading}
                error={error}
                message={message}
                onClearMessage={() => setMessage("")}
                loadError={loadError}
                context={outletContext}
                colorMode={colorMode}
                onToggleColorMode={toggleColorMode}
              />
            }
          >
            <Route index element={<DashboardPage />} />
            <Route path="company" element={<CompanyPage />} />
            <Route path="promotions" element={<PromotionPage />} />
            <Route path="bot-review" element={<BotReviewPage />} />
            <Route path="factors" element={<FactorsPage />} />
            <Route path="collector" element={<CollectorPage />} />
            <Route path="political" element={<PoliticalPage />} />
            <Route path="trades" element={<TradesPage />} />
            <Route path="backtest-runs" element={<BacktestRunsPage />} />
            <Route path="presets" element={<PresetsPage />} />
            <Route path="explorations" element={<ExplorationsPage />} />
            <Route path="decisions" element={<DecisionsPage />} />
            <Route path="evolution" element={<EvolutionPage />} />
            <Route path="library" element={<LibraryPage />} />
            <Route path="ai-explore" element={<AiExplorePage />} />
            <Route path="charts" element={<ChartsPage />} />
            <Route path="fundamentals" element={<FundamentalsPage />} />
            <Route path="backtest" element={<BacktestToolsPage />} />
          </Route>
        </Routes>
      </BrowserRouter>

      {/* 編輯 Bot 的彈出視窗（常駐，不隨路由切換消失） */}
      <EditBotDialog
        editBot={editBot}
        setEditBot={setEditBot}
        onSave={handleEditSave}
      />

      {/* 刪除 Bot 的確認視窗 */}
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

      {/* 停止 Bot 的確認視窗（停止 = 危險動作；實盤時文案加強提醒） */}
      <ConfirmDialog
        open={!!stopTarget}
        title="停止 Bot"
        message={
          stopTarget
            ? `確定要停止「${stopTarget.name}」嗎？停止後它將不再依排程監聽、也不會自動執行出場。${
                status?.live_armed ? "（目前為實盤模式，請特別確認手上部位。）" : ""
              }`
            : ""
        }
        confirmText="停止"
        confirmColor="warning"
        onConfirm={confirmStop}
        onClose={() => setStopTarget(null)}
      />
    </ThemeProvider>
  );
}

export default App;
