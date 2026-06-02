// ============================================================
// BacktestPanel：策略回測面板（表單 + 結果摘要 + 交易明細）
// ============================================================
// props：
//   btForm    — 回測表單值（{ strategy, symbol, days, initial_cash }）
//   setBtForm — 更新表單值
//   btResult  — 回測結果（還沒跑時是 null）
//   btLoading — 是否回測中（true 時按鈕變「回測中…」並停用）
//   onRun     — 按下「開始回測」時要跑的函式

import {
  Card,
  CardContent,
  Typography,
  Box,
  TextField,
  MenuItem,
  Button,
  Alert,
  Table,
  TableHead,
  TableBody,
  TableRow,
  TableCell,
  TableContainer,
  Paper,
} from "@mui/material";
import { STRATEGIES } from "../constants";
import Stat from "./Stat";

export default function BacktestPanel({
  btForm,
  setBtForm,
  btResult,
  btLoading,
  onRun,
}) {
  return (
    <Card sx={{ mb: 3 }}>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          策略回測
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          用歷史資料模擬策略表現，跟「單純買進持有」比較，看策略有沒有效。
        </Typography>
        <Box
          sx={{
            display: "grid",
            gridTemplateColumns: { xs: "1fr 1fr", sm: "repeat(4, 1fr)" },
            gap: 2,
            mb: 2,
          }}
        >
          <TextField
            select
            label="策略"
            value={btForm.strategy}
            onChange={(e) => setBtForm({ ...btForm, strategy: e.target.value })}
          >
            {STRATEGIES.map((s) => (
              <MenuItem key={s.value} value={s.value}>
                {s.label}
              </MenuItem>
            ))}
          </TextField>
          <TextField
            label="股票代號"
            value={btForm.symbol}
            onChange={(e) => setBtForm({ ...btForm, symbol: e.target.value })}
          />
          <TextField
            label="回測天數"
            type="number"
            value={btForm.days}
            onChange={(e) => setBtForm({ ...btForm, days: e.target.value })}
          />
          <TextField
            label="初始資金 (USD)"
            type="number"
            value={btForm.initial_cash}
            onChange={(e) =>
              setBtForm({ ...btForm, initial_cash: e.target.value })
            }
          />
        </Box>
        <Button variant="contained" onClick={onRun} disabled={btLoading}>
          {btLoading ? "回測中…" : "開始回測"}
        </Button>

        {/* 回測結果 */}
        {btResult && (
          <Box sx={{ mt: 3 }}>
            <Box
              sx={{
                display: "grid",
                gridTemplateColumns: {
                  xs: "1fr 1fr",
                  sm: "repeat(4, 1fr)",
                },
                gap: 2,
              }}
            >
              <Stat
                label="策略總報酬"
                value={`${btResult.total_return_pct}%`}
              />
              <Stat
                label="買進持有對照"
                value={`${btResult.buy_and_hold_pct}%`}
              />
              <Stat label="最大回撤" value={`${btResult.max_drawdown_pct}%`} />
              <Stat label="勝率" value={`${btResult.win_rate_pct}%`} />
              <Stat
                label="最終資產"
                value={`$${btResult.final_equity.toLocaleString()}`}
              />
              <Stat label="交易次數" value={btResult.num_trades} />
              <Stat label="完整買賣" value={btResult.num_round_trips} />
              <Stat label="資料天數" value={btResult.data_points} />
            </Box>

            {/* 一句話解讀 */}
            <Alert
              severity={
                btResult.total_return_pct >= btResult.buy_and_hold_pct
                  ? "success"
                  : "info"
              }
              sx={{ mt: 2 }}
            >
              {btResult.total_return_pct >= btResult.buy_and_hold_pct
                ? "👍 這次策略表現優於「單純買進持有」。"
                : "這次策略跑輸「單純買進持有」，可以調整參數或換策略再試試。"}
            </Alert>

            {/* 交易明細 */}
            {btResult.trades.length > 0 && (
              <TableContainer component={Paper} variant="outlined" sx={{ mt: 2 }}>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>日期</TableCell>
                      <TableCell>買/賣</TableCell>
                      <TableCell>價格</TableCell>
                      <TableCell>盈虧</TableCell>
                      <TableCell>原因</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {btResult.trades.map((t, idx) => (
                      <TableRow key={idx}>
                        <TableCell>{t.date}</TableCell>
                        <TableCell>
                          {t.side === "buy" ? "買進" : "賣出"}
                        </TableCell>
                        <TableCell>${t.price}</TableCell>
                        <TableCell
                          sx={{
                            color:
                              t.profit > 0
                                ? "success.main"
                                : t.profit < 0
                                ? "error.main"
                                : "text.secondary",
                          }}
                        >
                          {t.profit !== undefined ? `$${t.profit}` : "-"}
                        </TableCell>
                        <TableCell>{t.reason}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            )}
          </Box>
        )}
      </CardContent>
    </Card>
  );
}
