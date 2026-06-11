// ============================================================
// DecisionsPage：決策審計頁（/decisions）
// ============================================================
// Phase 9 step-06：把每個 Bot 的決策軌跡（為何在某時點買/賣/觀望/跳過）做成
// 可瀏覽頁——「每一筆自動決策可追溯」（原目標核心信條）的前端呈現。
// 只顯示後端寫好的 DecisionLog（Phase 6 step-08），不在前端重算決策。

import { useState } from "react";
import {
  Box,
  Typography,
  TextField,
  MenuItem,
  Paper,
  Table,
  TableHead,
  TableBody,
  TableRow,
  TableCell,
  TableContainer,
  Chip,
  Alert,
} from "@mui/material";
import { useOutletContext } from "react-router-dom";
import { api } from "../api";
// action → 標籤/配色映射抽到 utils 共用（卡片動畫、決策流也用同一套）
import { actionMeta } from "../utils/decisionMeta";

export default function DecisionsPage() {
  const { bots } = useOutletContext();
  const [botId, setBotId] = useState("");
  const [decisions, setDecisions] = useState([]);
  const [err, setErr] = useState("");

  async function selectBot(id) {
    setBotId(id);
    setErr("");
    setDecisions([]);
    if (id === "") return;
    try {
      setDecisions(await api.getBotDecisions(id));
    } catch (e) {
      setErr(e.message);
    }
  }

  return (
    <Box>
      <Typography variant="h4" sx={{ mb: 2 }}>
        決策審計
      </Typography>

      <TextField
        select
        size="small"
        label="選擇 Bot"
        value={botId}
        onChange={(e) => selectBot(e.target.value)}
        sx={{ minWidth: 220, mb: 2 }}
      >
        <MenuItem value="">— 請選擇 —</MenuItem>
        {bots.map((b) => (
          <MenuItem key={b.id} value={b.id}>
            {b.name}（{b.symbol}）
          </MenuItem>
        ))}
      </TextField>

      {err && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setErr("")}>
          {err}
        </Alert>
      )}

      {botId !== "" && (
        <TableContainer component={Paper} variant="outlined">
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>時間</TableCell>
                <TableCell>動作</TableCell>
                <TableCell>訊號</TableCell>
                <TableCell>標的</TableCell>
                <TableCell>參考價</TableCell>
                <TableCell>原因</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {decisions.length === 0 && (
                <TableRow>
                  <TableCell colSpan={6}>
                    <Typography variant="caption" color="text.secondary">
                      這個 Bot 還沒有決策紀錄。
                    </Typography>
                  </TableCell>
                </TableRow>
              )}
              {decisions.map((d) => {
                const meta = actionMeta(d.action);
                return (
                  <TableRow key={d.id}>
                    <TableCell>
                      {d.created_at ? new Date(d.created_at).toLocaleString() : "—"}
                    </TableCell>
                    <TableCell>
                      <Chip
                        size="small"
                        label={meta.label}
                        sx={{ color: meta.color, borderColor: meta.color }}
                        variant="outlined"
                      />
                    </TableCell>
                    <TableCell>{d.signal}</TableCell>
                    <TableCell>{d.symbol}</TableCell>
                    <TableCell>{d.price == null ? "—" : `$${d.price}`}</TableCell>
                    <TableCell>{d.reason}</TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </TableContainer>
      )}
    </Box>
  );
}
