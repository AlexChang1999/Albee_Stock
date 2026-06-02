// ============================================================
// TradesTable：交易紀錄表格
// ============================================================
// props：
//   trades — 交易紀錄陣列

import {
  Card,
  CardContent,
  Typography,
  Table,
  TableHead,
  TableBody,
  TableRow,
  TableCell,
  TableContainer,
  Paper,
} from "@mui/material";

export default function TradesTable({ trades }) {
  return (
    <Card sx={{ mb: 3 }}>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          交易紀錄（{trades.length}）
        </Typography>
        {trades.length === 0 ? (
          <Typography color="text.secondary">
            目前還沒有任何交易紀錄。
          </Typography>
        ) : (
          <TableContainer component={Paper} variant="outlined">
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>時間</TableCell>
                  <TableCell>股票</TableCell>
                  <TableCell>買/賣</TableCell>
                  <TableCell>股數</TableCell>
                  <TableCell>價格</TableCell>
                  <TableCell>原因</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {trades.map((t) => (
                  <TableRow key={t.id}>
                    <TableCell>
                      {new Date(t.created_at).toLocaleString()}
                    </TableCell>
                    <TableCell>{t.symbol}</TableCell>
                    <TableCell>{t.side === "buy" ? "買進" : "賣出"}</TableCell>
                    <TableCell>{t.qty}</TableCell>
                    <TableCell>${t.price}</TableCell>
                    <TableCell>{t.reason}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </CardContent>
    </Card>
  );
}
