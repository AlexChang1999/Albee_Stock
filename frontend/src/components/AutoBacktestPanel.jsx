// ============================================================
// AutoBacktestPanel：全自動掃描最佳策略（一鍵最強）
// ============================================================
// 概念：使用者不用懂策略、不用調參數，只要選股票按一顆按鈕，
//   程式自己把「8 種策略 × 各自參數組合」全跑一遍，依期望值 EV 排名，
//   挑出冠軍並列出完整排行榜（冠軍自動存進回測歷史並收藏）。
//
// 這個元件「自管狀態」（表單、載入中、結果、錯誤），不依賴 App，
// 跟 StrategyWorkbench 一樣是獨立區塊，放在儀表板分頁即可運作。

import { useState, useMemo } from "react";
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
  TableSortLabel,
  CircularProgress,
} from "@mui/material";
import { api } from "../api";
import { strategyLabel } from "../constants";
import { signOf, signedMoney } from "../utils/number";
import { NEON } from "../theme";

// 等寬字（數字對齊用，帳本感）
const MONO = { fontFamily: "var(--font-mono)" };

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

  // 排行榜排序（E2）：預設依 EV 由高到低；點欄位標頭可改排序鍵/方向
  const [orderBy, setOrderBy] = useState("expected_value");
  const [order, setOrder] = useState("desc");
  const handleSort = (key) => {
    if (orderBy === key) {
      setOrder((o) => (o === "desc" ? "asc" : "desc"));
    } else {
      setOrderBy(key);
      setOrder("desc"); // 換欄位先看「大的在前」最直覺
    }
  };
  const sortedBoard = useMemo(() => {
    const rows = result?.leaderboard ?? [];
    const dir = order === "desc" ? -1 : 1;
    // null 一律沉底（不論方向），數字照方向排
    return [...rows].sort((a, b) => {
      const av = a[orderBy];
      const bv = b[orderBy];
      if (av == null && bv == null) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;
      return (av - bv) * dir;
    });
  }, [result, orderBy, order]);

  // 可排序的數字欄（key 對應 leaderboard 摘要欄位）
  const SORT_COLS = [
    { key: "expected_value", label: "EV/筆" },
    { key: "expectancy_pct", label: "EV%" },
    { key: "total_return_pct", label: "報酬%" },
    { key: "win_rate_pct", label: "勝率%" },
    { key: "max_drawdown_pct", label: "回撤%" },
    { key: "num_round_trips", label: "交易" },
  ];

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
              bgcolor: "rgba(245,196,81,0.16)",
              color: NEON.magenta,
              fontWeight: 700,
              border: "1px solid rgba(245,196,81,0.35)",
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
                <Typography sx={{ fontSize: 13, fontWeight: 700, color: NEON.magenta, letterSpacing: "0.04em" }}>
                  🏆 冠軍策略
                </Typography>
              </Box>
              <Typography variant="h5" sx={{ mb: 0.3 }}>
                {strategyLabel(best.strategy_key)}
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
                {/* 漲跌數字一律補 +/- 號（signOf/signedMoney），不只靠紅綠顏色表達 */}
                <Metric
                  label="期望值 EV / 筆"
                  value={signedMoney(bm.expected_value)}
                  color={signColor(bm.expected_value)}
                  big
                />
                <Metric
                  label="EV 佔本金"
                  value={`${signOf(bm.expectancy_pct)}${bm.expectancy_pct}%`}
                  color={signColor(bm.expectancy_pct)}
                />
                <Metric
                  label="策略總報酬"
                  value={`${signOf(bm.total_return_pct)}${bm.total_return_pct}%`}
                  color={signColor(bm.total_return_pct)}
                />
                <Metric
                  label="買進持有對照"
                  value={`${signOf(bm.buy_and_hold_pct)}${bm.buy_and_hold_pct}%`}
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

            {/* 排行榜（點數字欄標頭可排序） */}
            <Typography variant="subtitle2" sx={{ mt: 3, mb: 1 }}>
              完整排行榜（點欄位標頭可排序，預設依 EV 由高到低）
            </Typography>
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>#</TableCell>
                    <TableCell>策略</TableCell>
                    <TableCell>參數</TableCell>
                    {SORT_COLS.map((col) => (
                      <TableCell
                        key={col.key}
                        align="right"
                        sortDirection={orderBy === col.key ? order : false}
                        aria-sort={
                          orderBy === col.key
                            ? order === "desc"
                              ? "descending"
                              : "ascending"
                            : undefined
                        }
                      >
                        <TableSortLabel
                          active={orderBy === col.key}
                          direction={orderBy === col.key ? order : "desc"}
                          onClick={() => handleSort(col.key)}
                        >
                          {col.label}
                        </TableSortLabel>
                      </TableCell>
                    ))}
                  </TableRow>
                </TableHead>
                <TableBody>
                  {sortedBoard.map((e, i) => {
                    // 冠軍列＝策略+參數與 best 相同（排序後位置會變，不能用 i===0 判斷）
                    const isChampion =
                      e.strategy_key === best.strategy_key &&
                      paramsText(e.params) === paramsText(best.params);
                    return (
                    <TableRow
                      key={`${e.strategy_key}-${paramsText(e.params)}`}
                      sx={{
                        // 冠軍那列淡金底
                        bgcolor: isChampion ? "rgba(176,136,58,0.08)" : "transparent",
                      }}
                    >
                      <TableCell sx={MONO}>
                        {isChampion ? "🏆" : i + 1}
                      </TableCell>
                      <TableCell sx={{ fontWeight: isChampion ? 700 : 500 }}>
                        {strategyLabel(e.strategy_key)}
                      </TableCell>
                      <TableCell sx={{ ...MONO, fontSize: 12, color: "text.secondary" }}>
                        {paramsText(e.params)}
                      </TableCell>
                      <TableCell align="right" sx={{ ...MONO, color: signColor(e.expected_value) }}>
                        {signOf(e.expected_value)}{e.expected_value}
                      </TableCell>
                      <TableCell align="right" sx={{ ...MONO, color: signColor(e.expectancy_pct) }}>
                        {signOf(e.expectancy_pct)}{e.expectancy_pct}
                      </TableCell>
                      <TableCell align="right" sx={{ ...MONO, color: signColor(e.total_return_pct) }}>
                        {signOf(e.total_return_pct)}{e.total_return_pct}
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
                    );
                  })}
                </TableBody>
              </Table>
            </TableContainer>
          </Box>
        )}
      </CardContent>
    </Card>
  );
}
