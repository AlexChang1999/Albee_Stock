// ============================================================
// AutoBacktestPanel：全自動掃描最佳策略（一鍵最強）
// ============================================================
// 概念：使用者不用懂策略、不用調參數，只要選股票按一顆按鈕，
//   程式自己把「8 種策略 × 各自參數組合」全跑一遍，依期望值 EV 排名，
//   挑出冠軍並列出完整排行榜（冠軍自動存進回測歷史並收藏）。
//
// 這個元件「自管狀態」（表單、載入中、結果、錯誤），不依賴 App，
// 跟 StrategyWorkbench 一樣是獨立區塊，放在儀表板分頁即可運作。

import { useState } from "react";
import {
  Card,
  CardContent,
  Typography,
  Box,
  TextField,
  MenuItem,
  Button,
  Alert,
  Chip,
  Table,
  TableHead,
  TableBody,
  TableRow,
  TableCell,
  TableContainer,
  CircularProgress,
} from "@mui/material";
import { api } from "../api";
import { STRATEGIES } from "../constants";

// 等寬字（數字對齊用，帳本感）
const MONO = { fontFamily: "var(--font-mono)" };

// 策略代號 -> 中文名稱
const STRATEGY_LABEL = Object.fromEntries(STRATEGIES.map((s) => [s.value, s.label]));

// 把參數 dict 轉成精簡字串，例如 {fast:12, slow:26} -> "fast 12 · slow 26"
function paramsText(params) {
  if (!params || Object.keys(params).length === 0) return "預設";
  return Object.entries(params)
    .map(([k, v]) => `${k} ${v}`)
    .join(" · ");
}

// 依數值正負給文字顏色（漲綠跌紅）
function signColor(v) {
  if (v > 0) return "success.main";
  if (v < 0) return "error.main";
  return "text.secondary";
}

// 小績效格：標籤在上、數字在下（數字用等寬字）
function Metric({ label, value, color, big }) {
  return (
    <Box>
      <Typography
        sx={{
          fontSize: 11,
          letterSpacing: "0.06em",
          textTransform: "uppercase",
          color: "text.secondary",
          fontWeight: 600,
        }}
      >
        {label}
      </Typography>
      <Typography
        sx={{
          ...MONO,
          fontSize: big ? 26 : 18,
          fontWeight: 600,
          color: color || "text.primary",
          mt: 0.3,
        }}
      >
        {value}
      </Typography>
    </Box>
  );
}

export default function AutoBacktestPanel() {
  // 表單（都有預設值，新手什麼都不改也能跑）
  const [form, setForm] = useState({
    symbol: "AAPL",
    days: 365,
    initial_cash: 10000,
    source: "alpaca",
  });
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  async function handleScan() {
    setError("");
    setResult(null);
    setLoading(true);
    try {
      const r = await api.autoBacktest({
        symbol: form.symbol.toUpperCase(),
        days: Number(form.days),
        initial_cash: Number(form.initial_cash),
        source: form.source,
      });
      setResult(r);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  const best = result?.best;
  const bm = best?.metrics; // 冠軍的完整指標

  return (
    <Card sx={{ mb: 3 }}>
      <CardContent>
        {/* 標題列 */}
        <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 0.5 }}>
          <Typography variant="h6">全自動掃描最佳策略</Typography>
          <Chip
            size="small"
            label="最強"
            sx={{
              bgcolor: "rgba(176,136,58,0.14)",
              color: "#8a6a25",
              fontWeight: 700,
              border: "1px solid rgba(176,136,58,0.3)",
            }}
          />
        </Box>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          不用懂策略、不用調參數——程式自己把所有策略與參數組合全跑一遍，
          依「期望值 EV」排名挑出最佳，並把冠軍存進回測歷史。
        </Typography>

        {/* 表單 */}
        <Box
          sx={{
            display: "grid",
            gridTemplateColumns: { xs: "1fr 1fr", sm: "repeat(4, 1fr)" },
            gap: 2,
            mb: 2,
          }}
        >
          <TextField
            label="股票代號"
            value={form.symbol}
            onChange={(e) => setForm({ ...form, symbol: e.target.value })}
          />
          <TextField
            label="回測天數"
            type="number"
            value={form.days}
            onChange={(e) => setForm({ ...form, days: e.target.value })}
          />
          <TextField
            label="初始資金 (USD)"
            type="number"
            value={form.initial_cash}
            onChange={(e) => setForm({ ...form, initial_cash: e.target.value })}
          />
          <TextField
            select
            label="資料源"
            value={form.source}
            onChange={(e) => setForm({ ...form, source: e.target.value })}
          >
            <MenuItem value="alpaca">Alpaca</MenuItem>
            <MenuItem value="yfinance">yfinance（免費）</MenuItem>
          </TextField>
        </Box>

        <Button
          variant="contained"
          onClick={handleScan}
          disabled={loading}
          startIcon={
            loading ? <CircularProgress size={16} color="inherit" /> : null
          }
        >
          {loading ? "掃描中…" : "一鍵全自動掃描"}
        </Button>

        {error && (
          <Alert severity="error" sx={{ mt: 2 }}>
            {error}
          </Alert>
        )}

        {/* ===== 結果 ===== */}
        {result && best && (
          <Box sx={{ mt: 3 }}>
            {/* 掃描統計 */}
            <Typography variant="caption" color="text.secondary">
              已測試 {result.combos_tested} 組組合（{result.strategies_tested} 種策略）·
              資料 {result.data_points} 天 · 冠軍與各策略最佳已存入回測歷史
            </Typography>

            {/* 冠軍卡片（金色強調） */}
            <Box
              sx={{
                mt: 1.5,
                p: 2.5,
                borderRadius: "16px",
                border: "1px solid rgba(176,136,58,0.35)",
                background:
                  "linear-gradient(135deg, rgba(176,136,58,0.08), rgba(31,111,84,0.05))",
              }}
            >
              <Box sx={{ display: "flex", alignItems: "baseline", gap: 1, mb: 0.5 }}>
                <Typography sx={{ fontSize: 13, fontWeight: 700, color: "#8a6a25", letterSpacing: "0.04em" }}>
                  🏆 冠軍策略
                </Typography>
              </Box>
              <Typography variant="h5" sx={{ mb: 0.3 }}>
                {STRATEGY_LABEL[best.strategy_key] || best.strategy_key}
              </Typography>
              <Typography sx={{ ...MONO, fontSize: 13, color: "text.secondary", mb: 2 }}>
                {paramsText(best.params)}
              </Typography>

              {/* 冠軍關鍵指標 */}
              <Box
                sx={{
                  display: "grid",
                  gridTemplateColumns: { xs: "1fr 1fr", sm: "repeat(4, 1fr)" },
                  gap: 2,
                }}
              >
                <Metric
                  label="期望值 EV / 筆"
                  value={`$${bm.expected_value}`}
                  color={signColor(bm.expected_value)}
                  big
                />
                <Metric
                  label="EV 佔本金"
                  value={`${bm.expectancy_pct}%`}
                  color={signColor(bm.expectancy_pct)}
                />
                <Metric
                  label="策略總報酬"
                  value={`${bm.total_return_pct}%`}
                  color={signColor(bm.total_return_pct)}
                />
                <Metric
                  label="買進持有對照"
                  value={`${bm.buy_and_hold_pct}%`}
                  color={signColor(bm.buy_and_hold_pct)}
                />
                <Metric label="勝率" value={`${bm.win_rate_pct}%`} />
                <Metric
                  label="最大回撤"
                  value={`${bm.max_drawdown_pct}%`}
                  color="error.main"
                />
                <Metric
                  label="獲利因子"
                  value={bm.profit_factor ?? "無虧損"}
                />
                <Metric label="完整買賣" value={bm.num_round_trips} />
              </Box>
            </Box>

            {/* 排行榜 */}
            <Typography variant="subtitle2" sx={{ mt: 3, mb: 1 }}>
              完整排行榜（依 EV 由高到低）
            </Typography>
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>#</TableCell>
                    <TableCell>策略</TableCell>
                    <TableCell>參數</TableCell>
                    <TableCell align="right">EV/筆</TableCell>
                    <TableCell align="right">EV%</TableCell>
                    <TableCell align="right">報酬%</TableCell>
                    <TableCell align="right">勝率%</TableCell>
                    <TableCell align="right">回撤%</TableCell>
                    <TableCell align="right">交易</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {result.leaderboard.map((e, i) => (
                    <TableRow
                      key={i}
                      sx={{
                        // 冠軍那列淡金底
                        bgcolor: i === 0 ? "rgba(176,136,58,0.08)" : "transparent",
                      }}
                    >
                      <TableCell sx={MONO}>
                        {i === 0 ? "🏆" : i + 1}
                      </TableCell>
                      <TableCell sx={{ fontWeight: i === 0 ? 700 : 500 }}>
                        {STRATEGY_LABEL[e.strategy_key] || e.strategy_key}
                      </TableCell>
                      <TableCell sx={{ ...MONO, fontSize: 12, color: "text.secondary" }}>
                        {paramsText(e.params)}
                      </TableCell>
                      <TableCell align="right" sx={{ ...MONO, color: signColor(e.expected_value) }}>
                        {e.expected_value}
                      </TableCell>
                      <TableCell align="right" sx={{ ...MONO, color: signColor(e.expectancy_pct) }}>
                        {e.expectancy_pct}
                      </TableCell>
                      <TableCell align="right" sx={{ ...MONO, color: signColor(e.total_return_pct) }}>
                        {e.total_return_pct}
                      </TableCell>
                      <TableCell align="right" sx={MONO}>
                        {e.win_rate_pct}
                      </TableCell>
                      <TableCell align="right" sx={{ ...MONO, color: "error.main" }}>
                        {e.max_drawdown_pct}
                      </TableCell>
                      <TableCell align="right" sx={MONO}>
                        {e.num_round_trips}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </Box>
        )}
      </CardContent>
    </Card>
  );
}
