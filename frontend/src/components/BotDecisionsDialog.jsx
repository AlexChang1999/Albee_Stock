// ============================================================
// BotDecisionsDialog：某個 Bot 的「決策審計軌跡」彈出視窗
// ============================================================
// 把後端 GET /bots/{id}/decisions（Phase 6 step-08 DecisionLog）露出到 UI，
// 回答「為何在某時點買 / 賣 / 不動」——含沒成交但有決策的時點
// （觀望 / 續抱 / 休市跳過 / 購買力不足 / 熔斷）。自動跑真錢時的事後查驗依據。
//
// props：
//   bot     — 要看的 Bot 物件（null = 視窗關閉）
//   onClose — 關閉視窗
//
// 自包含：開啟（bot 變非 null）時自己抓資料，含 loading / 空 / 錯誤態。

import { useEffect, useState } from "react";
import {
  Dialog,
  DialogTitle,
  DialogContent,
  Table,
  TableHead,
  TableBody,
  TableRow,
  TableCell,
  TableContainer,
  Paper,
  Typography,
  CircularProgress,
  Box,
  Chip,
} from "@mui/material";
import { api } from "../api";

// action 代號 → 中文標籤 + 晶片色（對應 models/decision_log.py 的 ACTION_*）
const ACTION_META = {
  bought: { label: "買進", color: "success" },
  sold: { label: "賣出", color: "error" },
  hold: { label: "觀望／續抱", color: "default" },
  skipped_market_closed: { label: "休市跳過", color: "default" },
  skipped_no_buying_power: { label: "購買力不足", color: "warning" },
  skipped_circuit_breaker: { label: "熔斷跳過", color: "warning" },
};

// signal 代號 → 中文
const SIGNAL_LABEL = { buy: "買進", sell: "賣出", hold: "觀望" };

export default function BotDecisionsDialog({ bot, onClose }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const botId = bot?.id;

  // 開啟（botId 有值）時抓最近決策；關閉或換 Bot 會重抓。
  useEffect(() => {
    if (botId == null) return;
    let cancelled = false;
    // 開窗時去後端抓資料是 effect 的正當用途（與外部系統同步）；
    // 這三個同步 setState 是刻意重置載入狀態，關閉該規則誤報。
    /* eslint-disable react-hooks/set-state-in-effect */
    setLoading(true);
    setError("");
    setRows([]);
    /* eslint-enable react-hooks/set-state-in-effect */
    api
      .getBotDecisions(botId)
      .then((data) => {
        if (!cancelled) setRows(data);
      })
      .catch((e) => {
        if (!cancelled) setError(e.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [botId]);

  return (
    <Dialog open={!!bot} onClose={onClose} fullWidth maxWidth="md">
      <DialogTitle>
        決策軌跡{bot ? `：${bot.name}` : ""}
      </DialogTitle>
      <DialogContent>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
          最近 50 筆決策（含沒成交但有決策的時點：觀望／休市／購買力不足／熔斷）。
        </Typography>

        {loading && (
          <Box sx={{ display: "flex", justifyContent: "center", py: 4 }}>
            <CircularProgress size={28} />
          </Box>
        )}

        {!loading && error && (
          <Typography color="error.main" sx={{ py: 2 }}>
            載入失敗：{error}
          </Typography>
        )}

        {!loading && !error && rows.length === 0 && (
          <Typography color="text.secondary" sx={{ py: 2 }}>
            這個 Bot 還沒有決策紀錄（啟動並執行後才會累積）。
          </Typography>
        )}

        {!loading && !error && rows.length > 0 && (
          <TableContainer
            component={Paper}
            variant="outlined"
            sx={{ maxHeight: 480 }}
          >
            <Table size="small" stickyHeader>
              <TableHead>
                <TableRow>
                  <TableCell>時間</TableCell>
                  <TableCell>訊號</TableCell>
                  <TableCell>動作</TableCell>
                  <TableCell align="right">參考價</TableCell>
                  <TableCell>原因</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {rows.map((r) => {
                  const meta = ACTION_META[r.action] || {
                    label: r.action,
                    color: "default",
                  };
                  return (
                    <TableRow key={r.id}>
                      <TableCell>
                        {r.created_at
                          ? new Date(r.created_at).toLocaleString()
                          : "—"}
                      </TableCell>
                      <TableCell>{SIGNAL_LABEL[r.signal] || r.signal}</TableCell>
                      <TableCell>
                        {/* 動作用晶片 + 文字（不只靠顏色表達買綠賣紅） */}
                        <Chip size="small" color={meta.color} label={meta.label} />
                      </TableCell>
                      <TableCell
                        align="right"
                        sx={{ fontVariantNumeric: "tabular-nums" }}
                      >
                        {r.price != null ? `$${r.price}` : "—"}
                      </TableCell>
                      <TableCell>{r.reason || "—"}</TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </DialogContent>
    </Dialog>
  );
}
