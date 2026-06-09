// ============================================================
// FactorsPage：因子數值表 / 報表（/factors）
// ============================================================
// Phase 10 step-03：把市場狀態因子（regime_features 的 7 因子 + regime 標籤）落表後，
// 在這頁查詢 / 匯出。**因子是觀測佐證、給人和回測看的報表，不是交易訊號**——本頁純呈現，
// 不下單、不重算因子（數字一律來自後端）。
//
// 設計：沿用既有表格頁風格（TradesPage / BacktestRunsPage）與深藍主題（吃 theme/NEON）。

import { useState, useEffect, useCallback } from "react";
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

// 數字格式：None/缺值顯示 "—"，否則四捨五入到指定位數
function fmt(v, digits = 2) {
  return v === null || v === undefined ? "—" : Number(v).toFixed(digits);
}

// regime 標籤的中文對照（純顯示）
const REGIME_LABEL = {
  trending: "趨勢",
  ranging: "盤整",
  high_volume_stall: "爆量滯漲",
  high_volatility: "高波動",
  unknown: "資料不足",
};

export default function FactorsPage() {
  const [symbol, setSymbol] = useState("");
  const [rows, setRows] = useState([]);
  const [err, setErr] = useState("");

  const load = useCallback(async () => {
    setErr("");
    try {
      setRows(await api.getFactors({ symbol: symbol.trim().toUpperCase() || undefined }));
    } catch (e) {
      setErr(e.message);
    }
  }, [symbol]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load();
    // 只在首次載入；之後由「查詢」鈕觸發（避免每打一字就打 API）
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const csvHref = api.factorsCsvUrl(symbol.trim().toUpperCase() || undefined);

  return (
    <Box>
      <Typography variant="h4" sx={{ mb: 1 }}>
        因子報表
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        常駐掃描每輪順手把 watchlist 各檔的市場狀態因子落表。因子是「觀測佐證」，不是交易訊號。
      </Typography>

      <Stack direction="row" spacing={2} alignItems="center" sx={{ mb: 2 }}>
        <TextField
          size="small"
          label="股票代號（留空看全部）"
          value={symbol}
          onChange={(e) => setSymbol(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && load()}
          sx={{ width: 220 }}
        />
        <Button size="small" variant="outlined" onClick={load}>
          查詢
        </Button>
        <Button size="small" variant="text" component="a" href={csvHref} target="_blank" rel="noopener">
          匯出 CSV
        </Button>
      </Stack>

      {err && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setErr("")}>
          {err}
        </Alert>
      )}

      <Card variant="outlined">
        <CardContent>
          {rows.length === 0 ? (
            <Typography color="text.secondary">
              還沒有因子快照（常駐掃描盤中跑起來後會自動累積）。
            </Typography>
          ) : (
            <TableContainer component={Paper} variant="outlined">
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>股票</TableCell>
                    <TableCell>時點</TableCell>
                    <TableCell>狀態</TableCell>
                    <TableCell align="right">量比</TableCell>
                    <TableCell align="right">5日報酬</TableCell>
                    <TableCell align="right">20日報酬</TableCell>
                    <TableCell align="right">波動(年化)</TableCell>
                    <TableCell align="right">趨勢強度</TableCell>
                    <TableCell align="right">ATR%</TableCell>
                    <TableCell align="right">區間位置</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {rows.map((r) => (
                    <TableRow key={r.id}>
                      <TableCell>{r.symbol}</TableCell>
                      <TableCell>{r.as_of ? r.as_of.slice(0, 10) : "—"}</TableCell>
                      <TableCell>
                        <Chip size="small" label={REGIME_LABEL[r.regime] || r.regime || "—"} />
                      </TableCell>
                      <TableCell align="right">{fmt(r.volume_ratio)}</TableCell>
                      <TableCell align="right">{fmt(r.return_5d, 4)}</TableCell>
                      <TableCell align="right">{fmt(r.return_20d, 4)}</TableCell>
                      <TableCell align="right">{fmt(r.volatility_20d, 4)}</TableCell>
                      <TableCell align="right">{fmt(r.trend_strength)}</TableCell>
                      <TableCell align="right">{fmt(r.atr_pct, 4)}</TableCell>
                      <TableCell align="right">{fmt(r.range_position)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </CardContent>
      </Card>
    </Box>
  );
}
