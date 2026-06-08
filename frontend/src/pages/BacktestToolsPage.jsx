// ============================================================
// BacktestToolsPage：回測 / 交易（step-01 暫時落腳處）
// ============================================================
// Phase 9 step-01：Dashboard 瘦身時，把 AutoBacktestPanel / BacktestPanel 從儀表板
// 搬出來，暫放這頁（執行回測的工具）。
// step-02 已把交易紀錄拆到 /trades；step-03 會把回測歷史拆到 /backtest-runs。

import { Box } from "@mui/material";
import { useOutletContext } from "react-router-dom";
import AutoBacktestPanel from "../components/AutoBacktestPanel";
import BacktestPanel from "../components/BacktestPanel";

export default function BacktestToolsPage() {
  const { btForm, setBtForm, btResult, btLoading, onBacktest } =
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
    </Box>
  );
}
