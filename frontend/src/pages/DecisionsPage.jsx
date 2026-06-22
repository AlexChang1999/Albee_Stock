// ============================================================
// DecisionsPage：決策審計頁（/decisions）
// ============================================================
// Phase 9 step-06：把每個 Bot 的決策軌跡（為何在某時點買/賣/觀望/跳過）做成
// 可瀏覽頁——「每一筆自動決策可追溯」（原目標核心信條）的前端呈現。
// 只顯示後端寫好的 DecisionLog（Phase 6 step-08），不在前端重算決策。
//
// Phase 15：表格補「量（成交量）」「股數」欄 + 指標快照 tooltip；頁首加「📖 讀教訓」鈕
// 把這支 Bot 的決策史餵本機 LLM 產一段檢討摘要（下次讀懂教訓）。

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
  Tooltip,
  Button,
  Stack,
  Alert,
  CircularProgress,
} from "@mui/material";
import { useOutletContext } from "react-router-dom";
import { api } from "../api";
// action → 標籤/配色映射抽到 utils 共用（卡片動畫、決策流也用同一套）
import { actionMeta } from "../utils/decisionMeta";

// 數字格式：量帶千分位、缺值 "—"
function fmtVolume(v) {
  return v === null || v === undefined ? "—" : Number(v).toLocaleString();
}

// 指標快照 dict → 一行可讀字串（給 tooltip）
function fmtIndicators(inds) {
  if (!inds || typeof inds !== "object") return "";
  return Object.entries(inds)
    .map(([k, v]) => `${k}: ${typeof v === "number" ? v.toFixed(2) : v}`)
    .join(" · ");
}

export default function DecisionsPage() {
  const { bots } = useOutletContext();
  const [botId, setBotId] = useState("");
  const [decisions, setDecisions] = useState([]);
  const [err, setErr] = useState("");
  // 「讀教訓」狀態（LLM 摘要）
  const [lessons, setLessons] = useState("");
  const [lessonsBusy, setLessonsBusy] = useState(false);
  const [lessonsErr, setLessonsErr] = useState("");

  async function selectBot(id) {
    setBotId(id);
    setErr("");
    setDecisions([]);
    setLessons("");
    setLessonsErr("");
    if (id === "") return;
    try {
      setDecisions(await api.getBotDecisions(id));
    } catch (e) {
      setErr(e.message);
    }
  }

  async function readLessons() {
    if (botId === "") return;
    setLessonsBusy(true);
    setLessonsErr("");
    setLessons("");
    try {
      const r = await api.getBotLessons(botId);
      setLessons(r.lessons || "（沒有回覆）");
    } catch (e) {
      setLessonsErr(e.message);
    } finally {
      setLessonsBusy(false);
    }
  }

  return (
    <Box>
      <Typography variant="h4" sx={{ mb: 2 }}>
        決策審計
      </Typography>

      <Stack direction="row" spacing={2} alignItems="center" sx={{ mb: 2 }}>
        <TextField
          select
          size="small"
          label="選擇 Bot"
          value={botId}
          onChange={(e) => selectBot(e.target.value)}
          sx={{ minWidth: 220 }}
        >
          <MenuItem value="">— 請選擇 —</MenuItem>
          {bots.map((b) => (
            <MenuItem key={b.id} value={b.id}>
              {b.name}（{b.symbol}）
            </MenuItem>
          ))}
        </TextField>

        <Button
          variant="outlined"
          onClick={readLessons}
          disabled={botId === "" || lessonsBusy}
          startIcon={lessonsBusy ? <CircularProgress size={16} /> : null}
        >
          {lessonsBusy ? "思考中…" : "📖 讀教訓"}
        </Button>
      </Stack>

      {err && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setErr("")}>
          {err}
        </Alert>
      )}
      {lessonsErr && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setLessonsErr("")}>
          {lessonsErr}
        </Alert>
      )}
      {lessons && (
        <Alert severity="info" sx={{ mb: 2, whiteSpace: "pre-wrap" }} onClose={() => setLessons("")}>
          {lessons}
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
                <TableCell align="right">參考價</TableCell>
                <TableCell align="right">量</TableCell>
                <TableCell align="right">股數</TableCell>
                <TableCell>原因</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {decisions.length === 0 && (
                <TableRow>
                  <TableCell colSpan={8}>
                    <Typography variant="caption" color="text.secondary">
                      這個 Bot 還沒有決策紀錄。
                    </Typography>
                  </TableCell>
                </TableRow>
              )}
              {decisions.map((d) => {
                const meta = actionMeta(d.action);
                const indText = fmtIndicators(d.indicators);
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
                    <TableCell align="right">{d.price == null ? "—" : `$${d.price}`}</TableCell>
                    <TableCell align="right">{fmtVolume(d.volume)}</TableCell>
                    <TableCell align="right">{d.qty == null ? "—" : d.qty}</TableCell>
                    <TableCell>
                      {indText && (
                        <Tooltip title={`觸發當下指標 → ${indText}`} arrow>
                          <Chip
                            size="small"
                            label="指標"
                            variant="outlined"
                            sx={{ mr: 1, color: "text.secondary", cursor: "help" }}
                          />
                        </Tooltip>
                      )}
                      {d.reason}
                    </TableCell>
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
