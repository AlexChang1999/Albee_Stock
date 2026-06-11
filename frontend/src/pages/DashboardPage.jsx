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

export default function DashboardPage() {
  const { account, bots, loading, onToggleActive, onRun, onEdit, onDelete, reload } =
    useOutletContext();
  const navigate = useNavigate();

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
      />
    </Box>
  );
}
