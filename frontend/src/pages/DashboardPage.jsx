// ============================================================
// DashboardPage：監控中心（瘦身後的儀表板）
// ============================================================
// Phase 9 step-01：原儀表板分頁瘦身成「純監控中心」——只留帳戶總覽 +
// AI 燈號 + 服役中 Bot。回測 / 交易表已搬到各自頁（/backtest、後續 /trades）。
//
// 共享資料/動作由 SidebarLayout 的 <Outlet context> 提供，這裡用
// useOutletContext() 取，行為與原 App tab 0 一致。

import { Box, Alert, Button } from "@mui/material";
import { useNavigate, useOutletContext } from "react-router-dom";
import AccountCard from "../components/AccountCard";
import PositionsCard from "../components/PositionsCard";
import BotList from "../components/BotList";
import AutomationPanel from "../components/AutomationPanel";
import DecisionFeed from "../components/DecisionFeed";
import BotStrategyChart from "../components/BotStrategyChart";
import { useBotActivity } from "../hooks/useBotActivity";

export default function DashboardPage() {
  const { account, bots, loading, onToggleActive, onRun, onEdit, onDelete, reload } =
    useOutletContext();
  const navigate = useNavigate();
  // Bot 即時活動（WS 真事件）：卡片動畫吃 activityByBot、決策流吃 feed；
  // 斷線時卡片傳 null 優雅降級回輪詢顯示
  const { connected, activityByBot, feed } = useBotActivity();

  return (
    <Box>
      <AccountCard account={account} />
      <PositionsCard />
      {/* AI 市場燈號：引導去「AI 探勘」一鍵部署（原 setTab(1) 改 navigate） */}
      <Alert
        severity="info"
        sx={{ mb: 2 }}
        action={
          <Button color="inherit" size="small" onClick={() => navigate("/ai-explore")}>
            前往 AI 探勘
          </Button>
        }
      >
        想新增 Bot？讓 AI 盤前海選幫你挑高期望值（EV）策略，檢閱後一鍵部署。
      </Alert>
      {/* 模式 B 全自動護欄：唯讀規則狀態 + 手動試跑（試跑會建 Paper Bot，故需 reload） */}
      <AutomationPanel onChanged={reload} />
      <BotList
        bots={bots}
        loading={loading}
        onToggle={onToggleActive}
        onRun={onRun}
        onEdit={onEdit}
        onDelete={onDelete}
        onShowDecisions={() => navigate("/decisions")}
        activityByBot={connected ? activityByBot : null}
      />
      {/* 決策即時流：每輪決策（含觀望）即時滑入，像看機器人的思考日誌 */}
      <DecisionFeed feed={feed} />
      {/* 策略視角：選 Bot 看指標疊圖 + 真實買賣 ▲▼ 標記（策略可視化） */}
      <BotStrategyChart bots={bots} />
    </Box>
  );
}
