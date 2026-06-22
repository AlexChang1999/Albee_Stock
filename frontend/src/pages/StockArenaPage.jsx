// ============================================================
// StockArenaPage：個股策略擂台（/stock-arena）
// ============================================================
// Phase 14：使用者的核心訴求「每檔股票用多個策略回測、找最佳模型」。
//   輸入一檔股票 → 後端 /auto-backtest 跑遍 9 策略 × 參數網格、依樣本外(OOS) EV 排名，
//   這頁把排行榜畫出來；每列可「部署成 paper bot」讓勝出策略對這檔股票虛擬交易，
//   之後由汰弱審查員（bot-review）排出每股實跑適配。回測排名 + 虛擬交易，兩者都做。
//
// 純呈現：EV 一律後端算（含成本 / 隔日成交 / OOS 切分），前端不重算。
// 顏色吃 theme/NEON，不寫死 hex。

import { useState, useCallback } from "react";
import {
  Box,
  Typography,
  Stack,
  TextField,
  Button,
  Alert,
  Card,
  CardContent,
  Table,
  TableHead,
  TableBody,
  TableRow,
  TableCell,
  TableContainer,
  Paper,
  Chip,
} from "@mui/material";
import { api } from "../api";
import { NEON } from "../theme";

// 數字格式：缺值 "—"，否則固定小數
function fmt(v, digits = 2) {
  return v === null || v === undefined ? "—" : Number(v).toFixed(digits);
}

export default function StockArenaPage() {
  const [symbol, setSymbol] = useState("AAPL");
  const [days, setDays] = useState(365);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [deployKey, setDeployKey] = useState(null); // 正在部署哪一列（strategy_key）

  const runScan = useCallback(async () => {
    setErr("");
    setMsg("");
    setResult(null);
    setLoading(true);
    try {
      const r = await api.autoBacktest({
        symbol: symbol.toUpperCase(),
        days: Number(days),
        initial_cash: 10000,
      });
      setResult(r);
    } catch (e) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  }, [symbol, days]);

  // 把某列策略部署成 paper bot（對這檔股票虛擬交易），跑起來餵 bot-review 適配排行。
  const deployRow = useCallback(
    async (entry) => {
      setErr("");
      setMsg("");
      setDeployKey(entry.strategy_key);
      try {
        const sym = (result?.symbol || symbol).toUpperCase();
        const bot = await api.createBot({
          name: `Arena-${sym}-${entry.strategy_key}`,
          strategy: entry.strategy_key,
          symbol: sym,
          params: entry.params || {},
          trade_amount: 1000,
        });
        await api.startBot(bot.id); // 立刻掛排程開始虛擬交易（全程 paper）
        setMsg(`已部署 paper bot：${sym} · ${entry.strategy_key}（每股策略虛擬交易，之後看汰弱審查員適配排行）`);
      } catch (e) {
        setErr(e.message);
      } finally {
        setDeployKey(null);
      }
    },
    [result, symbol]
  );

  const board = result?.leaderboard || [];

  return (
    <Box>
      <Typography variant="h4" sx={{ mb: 1 }}>
        個股策略擂台
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        輸入一檔股票，後端跑遍所有策略 × 參數、依<strong>樣本外 OOS EV</strong> 排名（含成本／隔日成交）。
        看中哪個策略就「部署成 paper bot」讓它對這檔股票虛擬交易；多個策略並存，最佳由汰弱審查員浮現。
      </Typography>

      <Stack direction="row" spacing={2} alignItems="center" sx={{ mb: 2 }}>
        <TextField
          size="small"
          label="股票代號"
          value={symbol}
          onChange={(e) => setSymbol(e.target.value)}
          sx={{ width: 140 }}
        />
        <TextField
          size="small"
          label="回看天數"
          type="number"
          value={days}
          onChange={(e) => setDays(e.target.value)}
          sx={{ width: 120 }}
        />
        <Button variant="contained" onClick={runScan} disabled={loading}>
          {loading ? "掃描中…（數十秒）" : "🏟️ 開跑擂台"}
        </Button>
      </Stack>

      {err && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setErr("")}>
          {err}
        </Alert>
      )}
      {msg && (
        <Alert severity="success" sx={{ mb: 2 }} onClose={() => setMsg("")}>
          {msg}
        </Alert>
      )}

      {result && (
        <Card variant="outlined">
          <CardContent>
            <Typography variant="h6" sx={{ mb: 1 }}>
              {result.symbol} 排行榜（{result.strategies_tested} 策略 · {result.combos_tested} 組合 · 依 OOS EV）
            </Typography>
            <TableContainer component={Paper} variant="outlined">
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>#</TableCell>
                    <TableCell>策略</TableCell>
                    <TableCell>參數</TableCell>
                    <TableCell align="right">OOS EV</TableCell>
                    <TableCell align="right">OOS 勝率%</TableCell>
                    <TableCell align="right">OOS 報酬%</TableCell>
                    <TableCell align="right">回合數</TableCell>
                    <TableCell align="right">部署</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {board.map((e, i) => (
                    <TableRow key={`${e.strategy_key}-${i}`}>
                      <TableCell>{i + 1}</TableCell>
                      <TableCell>{e.strategy_key}</TableCell>
                      <TableCell sx={{ maxWidth: 220, color: "text.secondary" }}>
                        <Typography variant="caption">{JSON.stringify(e.params)}</Typography>
                      </TableCell>
                      <TableCell align="right">
                        <Chip
                          size="small"
                          label={fmt(e.oos_expected_value)}
                          sx={{ color: (e.oos_expected_value ?? 0) >= 0 ? NEON.green : NEON.red }}
                        />
                      </TableCell>
                      <TableCell align="right">{fmt(e.oos_win_rate_pct, 1)}</TableCell>
                      <TableCell align="right">{fmt(e.oos_total_return_pct, 1)}</TableCell>
                      <TableCell align="right">{e.num_round_trips ?? "—"}</TableCell>
                      <TableCell align="right">
                        <Button
                          size="small"
                          variant="outlined"
                          disabled={deployKey === e.strategy_key}
                          onClick={() => deployRow(e)}
                        >
                          {deployKey === e.strategy_key ? "部署中…" : "部署成 bot"}
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </CardContent>
        </Card>
      )}
    </Box>
  );
}
