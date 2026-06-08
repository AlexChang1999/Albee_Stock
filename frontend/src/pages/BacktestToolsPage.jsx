// ============================================================
// BacktestToolsPage：回測 / 交易（step-01 暫時落腳處）
// ============================================================
// Phase 9 step-01：Dashboard 瘦身時，把 AutoBacktestPanel / BacktestPanel /
// TradesTable 從儀表板搬出來，暫放這頁，行為不變。
// 後續步驟會接手拆分：step-02 交易紀錄 → /trades；step-03 回測歷史 → /backtest-runs。

import { Box } from "@mui/material";
import { useOutletContext } from "react-router-dom";
import AutoBacktestPanel from "../components/AutoBacktestPanel";
import BacktestPanel from "../components/BacktestPanel";
import TradesTable from "../components/TradesTable";

export default function BacktestToolsPage() {
  const { btForm, setBtForm, btResult, btLoading, onBacktest, trades } =
    useOutletContext();

  return (
    <Box>
      {/* 全自動掃描最佳策略（一鍵最強） */}
      <AutoBacktestPanel />
      <BacktestPanel
        btForm={btForm}
        setBtForm={setBtForm}
        btResult={btResult}
        btLoading={btLoading}
        onRun={onBacktest}
      />
      <TradesTable trades={trades} />
    </Box>
  );
}
