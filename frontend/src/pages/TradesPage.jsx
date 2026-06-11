// ============================================================
// TradesPage：交易紀錄頁（/trades）
// ============================================================
// Phase 9 step-02：把原本埋在儀表板的 TradesTable 升級成獨立頁，
// 上方加篩選列（依 Bot / 標的 / 買賣別 / 日期）。
// 篩選一律前端純函式過濾（filterTrades），不改後端 /trades 端點。

import { useMemo, useState } from "react";
import {
  Box,
  Card,
  CardContent,
  Grid,
  TextField,
  MenuItem,
  Button,
  Typography,
} from "@mui/material";
import { useOutletContext } from "react-router-dom";
import TradesTable from "../components/TradesTable";
import { filterTrades } from "../utils/filterTrades";

const EMPTY = { botId: "", symbol: "", side: "", dateFrom: "", dateTo: "" };

export default function TradesPage() {
  const { trades, bots, loading } = useOutletContext();
  const [filters, setFilters] = useState(EMPTY);

  function set(field, value) {
    setFilters((f) => ({ ...f, [field]: value }));
  }

  const filtered = useMemo(
    () => filterTrades(trades, filters),
    [trades, filters]
  );

  return (
    <Box>
      <Typography variant="h4" sx={{ mb: 2 }}>
        交易紀錄
      </Typography>

      {/* 篩選列 */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Grid container spacing={2} alignItems="center">
            <Grid item xs={12} sm={6} md={2.4}>
              <TextField
                select
                fullWidth
                size="small"
                label="Bot"
                value={filters.botId}
                onChange={(e) => set("botId", e.target.value)}
              >
                <MenuItem value="">全部</MenuItem>
                {bots.map((b) => (
                  <MenuItem key={b.id} value={b.id}>
                    {b.name}
                  </MenuItem>
                ))}
              </TextField>
            </Grid>
            <Grid item xs={12} sm={6} md={2.4}>
              <TextField
                fullWidth
                size="small"
                label="標的"
                placeholder="例如 AAPL"
                value={filters.symbol}
                onChange={(e) => set("symbol", e.target.value)}
              />
            </Grid>
            <Grid item xs={12} sm={6} md={2.4}>
              <TextField
                select
                fullWidth
                size="small"
                label="買/賣"
                value={filters.side}
                onChange={(e) => set("side", e.target.value)}
              >
                <MenuItem value="">全部</MenuItem>
                <MenuItem value="buy">買進</MenuItem>
                <MenuItem value="sell">賣出</MenuItem>
              </TextField>
            </Grid>
            <Grid item xs={6} sm={6} md={2.4}>
              <TextField
                fullWidth
                size="small"
                type="date"
                label="起始日"
                InputLabelProps={{ shrink: true }}
                value={filters.dateFrom}
                onChange={(e) => set("dateFrom", e.target.value)}
              />
            </Grid>
            <Grid item xs={6} sm={6} md={2.4}>
              <TextField
                fullWidth
                size="small"
                type="date"
                label="結束日"
                InputLabelProps={{ shrink: true }}
                value={filters.dateTo}
                onChange={(e) => set("dateTo", e.target.value)}
              />
            </Grid>
          </Grid>
          <Box sx={{ mt: 2, display: "flex", alignItems: "center", gap: 2 }}>
            <Button size="small" onClick={() => setFilters(EMPTY)}>
              清除篩選
            </Button>
            <Typography variant="caption" color="text.secondary">
              共 {filtered.length} / {trades.length} 筆
            </Typography>
          </Box>
        </CardContent>
      </Card>

      <TradesTable trades={filtered} loading={loading} />
    </Box>
  );
}
