// ============================================================
// BacktestRunsPage：回測歷史 / EV 榜頁（/backtest-runs）
// ============================================================
// Phase 9 step-03：把原本埋在右側工作台的回測歷史，搬成獨立全頁。
//   - 依 EV 由高到低的榜（後端已排序，前端照顯示）
//   - 收藏標星（api.favoriteBacktestRun）
//   - 點一筆看完整 metrics + 資金曲線（api.getBacktestRun → BacktestResultCard + EquitySparkline）
//   - 勾選數筆並排比較 metrics（先做簡單並排，非分析套件）
// 不改後端排序語意；不重算 EV——只顯示後端結果。

import { useState, useEffect, useCallback } from "react";
import {
  Box,
  Typography,
  Button,
  Paper,
  Table,
  TableHead,
  TableBody,
  TableRow,
  TableCell,
  TableContainer,
  IconButton,
  Checkbox,
  Tooltip,
  Alert,
  Stack,
  Grid,
} from "@mui/material";
import { api } from "../api";
import { STRATEGIES } from "../constants";
import { NEON } from "../theme";
import BacktestResultCard from "../components/BacktestResultCard";
import EquitySparkline from "../components/EquitySparkline";

function strategyLabel(key) {
  return STRATEGIES.find((s) => s.value === key)?.label || key;
}

export default function BacktestRunsPage() {
  const [runs, setRuns] = useState([]);
  const [favOnly, setFavOnly] = useState(false);
  const [err, setErr] = useState("");

  // 點開的單筆完整內容（含 metrics + equity_curve）
  const [detail, setDetail] = useState(null);
  // 勾選要並排比較的 run id 集合
  const [compareIds, setCompareIds] = useState([]);
  const [compareData, setCompareData] = useState([]);

  const loadRuns = useCallback(async () => {
    try {
      setRuns(await api.getBacktestRuns(favOnly));
    } catch (e) {
      setErr(e.message);
    }
  }, [favOnly]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadRuns();
  }, [loadRuns]);

  async function openDetail(run) {
    setErr("");
    try {
      setDetail(await api.getBacktestRun(run.id));
    } catch (e) {
      setErr(e.message);
    }
  }

  async function toggleFavorite(run) {
    try {
      await api.favoriteBacktestRun(run.id, !run.is_good);
      loadRuns();
    } catch (e) {
      setErr(e.message);
    }
  }

  // 勾選 / 取消比較；勾選後抓完整 metrics 以便並排
  async function toggleCompare(run) {
    const exists = compareIds.includes(run.id);
    if (exists) {
      setCompareIds((ids) => ids.filter((id) => id !== run.id));
      setCompareData((arr) => arr.filter((d) => d.id !== run.id));
      return;
    }
    try {
      const full = await api.getBacktestRun(run.id);
      setCompareIds((ids) => [...ids, run.id]);
      setCompareData((arr) => [...arr, full]);
    } catch (e) {
      setErr(e.message);
    }
  }

  return (
    <Box>
      <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 2 }}>
        <Typography variant="h4">回測歷史 · EV 榜</Typography>
        <Button size="small" onClick={() => setFavOnly((v) => !v)}>
          {favOnly ? "顯示全部" : "只看好策略 ★"}
        </Button>
      </Stack>

      {err && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setErr("")}>
          {err}
        </Alert>
      )}

      <TableContainer component={Paper} variant="outlined" sx={{ mb: 3 }}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>★</TableCell>
              <TableCell>EV／筆</TableCell>
              <TableCell>策略 · 標的</TableCell>
              <TableCell>勝率</TableCell>
              <TableCell>報酬</TableCell>
              <TableCell>回撤</TableCell>
              <TableCell>檢討</TableCell>
              <TableCell>比較</TableCell>
              <TableCell>報表</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {runs.length === 0 && (
              <TableRow>
                <TableCell colSpan={9}>
                  <Typography variant="caption" color="text.secondary">
                    還沒有回測紀錄。
                  </Typography>
                </TableCell>
              </TableRow>
            )}
            {runs.map((run) => {
              const ev = run.expected_value;
              return (
                <TableRow
                  key={run.id}
                  hover
                  sx={{ cursor: "pointer" }}
                  onClick={() => openDetail(run)}
                >
                  <TableCell onClick={(e) => e.stopPropagation()}>
                    <IconButton size="small" onClick={() => toggleFavorite(run)}>
                      {run.is_good ? "★" : "☆"}
                    </IconButton>
                  </TableCell>
                  <TableCell
                    sx={{
                      color: (ev ?? 0) >= 0 ? NEON.green : NEON.red,
                      fontWeight: 700,
                    }}
                  >
                    {ev ?? "—"}
                  </TableCell>
                  <TableCell>
                    {strategyLabel(run.strategy_key)} · {run.symbol}
                  </TableCell>
                  <TableCell>{run.win_rate_pct ?? "—"}%</TableCell>
                  <TableCell>{run.total_return_pct ?? "—"}%</TableCell>
                  <TableCell>{run.max_drawdown_pct ?? "—"}%</TableCell>
                  <TableCell>{run.has_postmortem ? "已檢討" : "—"}</TableCell>
                  <TableCell onClick={(e) => e.stopPropagation()}>
                    <Checkbox
                      size="small"
                      checked={compareIds.includes(run.id)}
                      onChange={() => toggleCompare(run)}
                    />
                  </TableCell>
                  <TableCell onClick={(e) => e.stopPropagation()}>
                    <Tooltip title="開啟績效報表">
                      <IconButton
                        size="small"
                        onClick={() => window.open(api.reportUrl(run.id), "_blank")}
                      >
                        📊
                      </IconButton>
                    </Tooltip>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </TableContainer>

      {/* 並排比較（勾選 2 筆以上時顯示） */}
      {compareData.length > 0 && (
        <Box sx={{ mb: 3 }}>
          <Typography variant="h6" sx={{ mb: 1 }}>
            並排比較（{compareData.length}）
          </Typography>
          <Grid container spacing={2}>
            {compareData.map((d) => (
              <Grid item xs={12} sm={6} md={4} key={d.id}>
                <BacktestResultCard
                  metrics={d.metrics}
                  title={`#${d.id} ${strategyLabel(d.strategy_key)} · ${d.symbol}`}
                  runId={d.id}
                >
                  <EquitySparkline data={d.metrics?.equity_curve} />
                </BacktestResultCard>
              </Grid>
            ))}
          </Grid>
        </Box>
      )}

      {/* 單筆明細 */}
      {detail && (
        <Box sx={{ maxWidth: 420 }}>
          <Typography variant="h6" sx={{ mb: 1 }}>
            明細 · #{detail.id}
          </Typography>
          <BacktestResultCard
            metrics={detail.metrics}
            title={`${strategyLabel(detail.strategy_key)} · ${detail.symbol} · ${detail.period_days} 天`}
            runId={detail.id}
          >
            <EquitySparkline data={detail.metrics?.equity_curve} width={380} />
          </BacktestResultCard>
        </Box>
      )}
    </Box>
  );
}
