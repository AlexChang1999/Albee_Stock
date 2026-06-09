// ============================================================
// BacktestResultCard：回測結果卡（EV 當頭條）共用元件
// ============================================================
// Phase 9 step-03：原本只在 StrategyWorkbench 內聯的「回測結果卡」抽成共用元件，
// 讓策略工作台與回測歷史頁（/backtest-runs）共用同一套 EV 顯示，不重寫兩份。
//
// props：
//   metrics — 扁平指標物件（expected_value / win_rate_pct / profit_factor /
//             total_return_pct / max_drawdown_pct / num_round_trips / extended{sharpe,sortino}）
//   title   — 卡片標題（方案名稱，或「策略 · 標的」）
//   runId   — 有值時顯示「開啟完整績效報表」按鈕（連 api.reportUrl）
//   children — 額外內容（例如資金曲線 sparkline）

import { Box, Paper, Typography, Chip, Stack, Button, Alert } from "@mui/material";
import { NEON } from "../theme";
import { api } from "../api";

export default function BacktestResultCard({ metrics, title, runId, children }) {
  if (!metrics) return null;
  const ev = metrics.expected_value;
  const evPositive = (ev ?? 0) >= 0;

  return (
    <Paper variant="outlined" sx={{ p: 1.5 }}>
      {title && (
        <Typography variant="caption" color="text.secondary">
          {title}
        </Typography>
      )}

      {/* EV 頭條 */}
      <Box sx={{ my: 1, textAlign: "center" }}>
        <Typography variant="caption" color="text.secondary">
          期望值 EV／筆
        </Typography>
        <Typography
          variant="h4"
          sx={{
            fontFamily: '"Sora", sans-serif',
            fontWeight: 700,
            color: evPositive ? NEON.green : NEON.red,
          }}
        >
          {ev == null ? "—" : `${evPositive ? "+" : ""}${ev}`}
        </Typography>
      </Box>

      <Stack direction="row" flexWrap="wrap" gap={0.5} sx={{ mb: 1 }}>
        <Chip size="small" label={`勝率 ${metrics.win_rate_pct ?? "—"}%`} />
        <Chip size="small" label={`PF ${metrics.profit_factor ?? "—"}`} />
        <Chip size="small" label={`總報酬 ${metrics.total_return_pct ?? "—"}%`} />
        <Chip size="small" label={`回撤 ${metrics.max_drawdown_pct ?? "—"}%`} />
        <Chip size="small" label={`買賣 ${metrics.num_round_trips ?? "—"} 筆`} />
        {/* quantstats 風險調整後指標（有算出才顯示） */}
        {metrics.extended?.sharpe != null && (
          <Chip size="small" label={`Sharpe ${metrics.extended.sharpe}`} />
        )}
        {metrics.extended?.sortino != null && (
          <Chip size="small" label={`Sortino ${metrics.extended.sortino}`} />
        )}
      </Stack>

      {children}

      {runId && (
        <Button
          size="small"
          onClick={() => window.open(api.reportUrl(runId), "_blank")}
        >
          📊 開啟完整績效報表
        </Button>
      )}
      {ev != null && ev < 0 && (
        <Alert severity="warning" sx={{ mt: 1 }}>
          EV 為負（長期不賺）。可請 Claude 助手分析錯在哪。
        </Alert>
      )}
    </Paper>
  );
}
