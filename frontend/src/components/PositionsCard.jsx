// ============================================================
// PositionsCard：持倉卡片（含浮動損益）
// ============================================================
// 自含資料：掛載時自取 GET /positions，不經 App.jsx 的 Outlet context。
// 浮動損益用 signedMoney/signOf 補 +/- 號（不只靠紅綠色，無障礙），
// 顏色吃 theme 的 NEON（green 獲利 / red 虧損），不寫死 hex。

import { useEffect, useState } from "react";
import {
  Card,
  CardContent,
  Typography,
  Table,
  TableHead,
  TableBody,
  TableRow,
  TableCell,
} from "@mui/material";
import { api } from "../api";
import { NEON } from "../theme";
import { money, signedMoney, signOf, formatPercent } from "../utils/number";

export default function PositionsCard() {
  const [positions, setPositions] = useState(null); // null=載入中、[]=無持倉

  useEffect(() => {
    let alive = true;
    // 後端無金鑰/失敗時回空陣列；這裡再保險接住例外，避免整頁崩。
    api
      .getPositions()
      .then((data) => alive && setPositions(Array.isArray(data) ? data : []))
      .catch(() => alive && setPositions([]));
    return () => {
      alive = false;
    };
  }, []);

  // 依損益正負取色（0 視為中性，吃次要文字色）
  const plColor = (v) => (v > 0 ? NEON.green : v < 0 ? NEON.red : "text.secondary");

  return (
    <Card sx={{ mb: 3 }}>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          目前持倉
        </Typography>

        {positions === null ? (
          <Typography color="text.secondary">載入中…</Typography>
        ) : positions.length === 0 ? (
          <Typography color="text.secondary">目前無持倉</Typography>
        ) : (
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>代號</TableCell>
                <TableCell align="right">股數</TableCell>
                <TableCell align="right">均價</TableCell>
                <TableCell align="right">現價</TableCell>
                <TableCell align="right">市值</TableCell>
                <TableCell align="right">浮動損益</TableCell>
                <TableCell align="right">報酬率</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {positions.map((p) => (
                <TableRow key={p.symbol}>
                  <TableCell>{p.symbol}</TableCell>
                  <TableCell align="right">{p.qty}</TableCell>
                  <TableCell align="right">{money(p.avg_entry_price)}</TableCell>
                  <TableCell align="right">{money(p.current_price)}</TableCell>
                  <TableCell align="right">{money(p.market_value)}</TableCell>
                  {/* 損益帶 +/- 號 + 紅綠色（雙重編碼，色盲也讀得出方向） */}
                  <TableCell align="right" sx={{ color: plColor(p.unrealized_pl) }}>
                    {signedMoney(p.unrealized_pl)}
                  </TableCell>
                  <TableCell align="right" sx={{ color: plColor(p.unrealized_pl) }}>
                    {p.unrealized_plpc === null || p.unrealized_plpc === undefined
                      ? "—"
                      : `${signOf(p.unrealized_plpc)}${formatPercent(p.unrealized_plpc)}`}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}
