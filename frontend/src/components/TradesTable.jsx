// ============================================================
// TradesTable：交易紀錄表格（可排序）
// ============================================================
// props：
//   trades — 交易紀錄陣列

import { useState, useMemo } from "react";
import {
  Card,
  CardContent,
  Typography,
  Table,
  TableHead,
  TableBody,
  TableRow,
  TableCell,
  TableSortLabel,
  TableContainer,
  Paper,
} from "@mui/material";

// 可排序欄位定義：key 對應資料欄、numeric 決定右對齊與數值排序、time 走時間排序
const COLUMNS = [
  { key: "created_at", label: "時間", time: true },
  { key: "symbol", label: "股票" },
  { key: "side", label: "買/賣", sortable: false },
  { key: "qty", label: "股數", numeric: true },
  { key: "price", label: "價格", numeric: true },
  { key: "reason", label: "原因", sortable: false },
];

export default function TradesTable({ trades }) {
  // 預設依時間新→舊
  const [orderBy, setOrderBy] = useState("created_at");
  const [order, setOrder] = useState("desc");

  const sorted = useMemo(() => {
    const col = COLUMNS.find((c) => c.key === orderBy);
    const arr = [...trades];
    arr.sort((a, b) => {
      let av = a[orderBy];
      let bv = b[orderBy];
      if (col?.time) {
        av = new Date(a.created_at).getTime();
        bv = new Date(b.created_at).getTime();
      } else if (col?.numeric) {
        av = Number(av);
        bv = Number(bv);
      }
      if (av < bv) return order === "asc" ? -1 : 1;
      if (av > bv) return order === "asc" ? 1 : -1;
      return 0;
    });
    return arr;
  }, [trades, orderBy, order]);

  function handleSort(key) {
    if (orderBy === key) {
      setOrder((o) => (o === "asc" ? "desc" : "asc"));
    } else {
      setOrderBy(key);
      setOrder("asc");
    }
  }

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
          // maxHeight + stickyHeader：列多時表頭固定在頂、內容區自捲，看得到欄位名
          <TableContainer
            component={Paper}
            variant="outlined"
            sx={{ maxHeight: 420 }}
          >
            <Table size="small" stickyHeader>
              <TableHead>
                <TableRow>
                  {COLUMNS.map((c) => {
                    const active = orderBy === c.key;
                    return (
                      <TableCell
                        key={c.key}
                        align={c.numeric ? "right" : "left"}
                        // sortDirection 會輸出 aria-sort，供螢幕報讀知道目前排序
                        sortDirection={active ? order : false}
                      >
                        {c.sortable === false ? (
                          c.label
                        ) : (
                          <TableSortLabel
                            active={active}
                            direction={active ? order : "asc"}
                            onClick={() => handleSort(c.key)}
                          >
                            {c.label}
                          </TableSortLabel>
                        )}
                      </TableCell>
                    );
                  })}
                </TableRow>
              </TableHead>
              <TableBody>
                {sorted.map((t) => (
                  <TableRow key={t.id}>
                    <TableCell>
                      {new Date(t.created_at).toLocaleString()}
                    </TableCell>
                    <TableCell>{t.symbol}</TableCell>
                    <TableCell>{t.side === "buy" ? "買進" : "賣出"}</TableCell>
                    {/* 數字欄右對齊 + 等寬字（tabular-nums），上下列對齊不跳動 */}
                    <TableCell
                      align="right"
                      sx={{ fontVariantNumeric: "tabular-nums" }}
                    >
                      {t.qty}
                    </TableCell>
                    <TableCell
                      align="right"
                      sx={{ fontVariantNumeric: "tabular-nums" }}
                    >
                      ${t.price}
                    </TableCell>
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
