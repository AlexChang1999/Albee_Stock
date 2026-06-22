// ============================================================
// BotReviewPage：bot 汰弱審查員（/bot-review）
// ============================================================
// Phase 13：自動部署讓 Bot 數＝好策略×標的數會持續長。審查員每日考核 paper 艦隊、
// 記錄「哪檔股票適合哪個策略」（fit 排行）、軟汰弱不及格的 Bot。
//
// 本頁純呈現 + 一個「立即審查」鈕（叫後端跑一輪）。不在前端算績效、不直接動 Bot。
// 設計：沿用既有表格頁風格（FactorsPage）與深藍主題（顏色吃 MUI Chip 的語意色，不寫死 hex）。

import { useState, useEffect, useCallback } from "react";
import {
  Box,
  Typography,
  Stack,
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
  ToggleButton,
  ToggleButtonGroup,
} from "@mui/material";
import { api } from "../api";

// 數字格式：缺值顯示 "—"，否則固定小數位
function fmt(v, digits = 1) {
  return v === null || v === undefined ? "—" : Number(v).toFixed(digits);
}

// 評等 → 中文標籤 + MUI 語意色（吃主題，不寫死 hex）
const VERDICT = {
  good: { label: "適配", color: "success" },
  poor: { label: "不及格", color: "error" },
  insufficient: { label: "樣本不足", color: "default" },
};

// 把平鋪的 fit 列依標的分組（保留全域 good→poor 排序，故每組內也是好的在前）。
// 回 [[symbol, [fits]], ...]，標的依首次出現（＝全域排名）順序。
function groupBySymbol(fits) {
  const m = new Map();
  for (const f of fits) {
    if (!m.has(f.symbol)) m.set(f.symbol, []);
    m.get(f.symbol).push(f);
  }
  return [...m.entries()];
}

export default function BotReviewPage() {
  const [fits, setFits] = useState([]);
  const [culled, setCulled] = useState([]);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [running, setRunning] = useState(false);
  const [groupBy, setGroupBy] = useState("symbol"); // 預設依標的分組（每股策略競賽）

  const load = useCallback(async () => {
    setErr("");
    try {
      const [f, c] = await Promise.all([
        api.getBotReviewFits(),
        api.getBotReviewCulled(),
      ]);
      setFits(f);
      setCulled(c);
    } catch (e) {
      setErr(e.message);
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 手動跑一輪審查，跑完重載報表
  const runNow = useCallback(async () => {
    setErr("");
    setMsg("");
    setRunning(true);
    try {
      const s = await api.runBotReview();
      setMsg(
        `審查完成：考核 ${s.reviewed} 支、更新 fit ${s.fits_updated} 筆、` +
          `汰弱 ${s.culled} 支、樣本不足 ${s.skipped_insufficient} 支、失敗 ${s.failed} 支。`
      );
      await load();
    } catch (e) {
      setErr(e.message);
    } finally {
      setRunning(false);
    }
  }, [load]);

  return (
    <Box>
      <Typography variant="h4" sx={{ mb: 1 }}>
        汰弱審查員
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        每日考核 paper 艦隊：記錄「哪檔股票適合哪個策略」，並把實跑夠久卻不及格的 Bot 軟汰弱
        （停用 + 標記，資料保留可查）。下方為適配排行與汰弱紀錄。
      </Typography>

      <Stack direction="row" spacing={2} alignItems="center" sx={{ mb: 2 }}>
        <Button size="small" variant="contained" onClick={runNow} disabled={running}>
          {running ? "審查中…" : "立即審查一輪"}
        </Button>
        <Button size="small" variant="text" onClick={load} disabled={running}>
          重新整理
        </Button>
      </Stack>

      {err && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setErr("")}>
          {err}
        </Alert>
      )}
      {msg && (
        <Alert severity="success" sx={{ mb: 2 }} onClose={() => setMsg("")}>
          {msg}
        </Alert>
      )}

      {/* ── 策略×標的適配排行 ── */}
      <Stack direction="row" spacing={2} alignItems="center" sx={{ mb: 1 }}>
        <Typography variant="h6">策略 × 標的 適配排行</Typography>
        <ToggleButtonGroup
          size="small"
          exclusive
          value={groupBy}
          onChange={(e, v) => v && setGroupBy(v)}
        >
          <ToggleButton value="symbol">依標的分組</ToggleButton>
          <ToggleButton value="flat">平鋪</ToggleButton>
        </ToggleButtonGroup>
      </Stack>
      <Card variant="outlined" sx={{ mb: 3 }}>
        <CardContent>
          {fits.length === 0 ? (
            <Typography color="text.secondary">
              還沒有適配紀錄（paper Bot 累積夠交易、審查員跑過後會出現）。
            </Typography>
          ) : groupBy === "symbol" ? (
            // 每股一塊：這檔股票上各策略的實跑競賽（好的在前）
            groupBySymbol(fits).map(([sym, rows]) => (
              <Box key={sym} sx={{ mb: 2 }}>
                <Typography variant="subtitle1" sx={{ mb: 0.5 }}>
                  {sym}（{rows.length} 策略競賽）
                </Typography>
                <TableContainer component={Paper} variant="outlined">
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>策略</TableCell>
                        <TableCell>評等</TableCell>
                        <TableCell align="right">回合數</TableCell>
                        <TableCell align="right">勝率%</TableCell>
                        <TableCell align="right">報酬%</TableCell>
                        <TableCell align="right">最大回撤%</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {rows.map((r) => {
                        const v = VERDICT[r.verdict] || { label: r.verdict, color: "default" };
                        return (
                          <TableRow key={r.id}>
                            <TableCell>{r.strategy_key}</TableCell>
                            <TableCell>
                              <Chip size="small" color={v.color} label={v.label} />
                            </TableCell>
                            <TableCell align="right">{r.num_round_trips}</TableCell>
                            <TableCell align="right">{fmt(r.win_rate_pct)}</TableCell>
                            <TableCell align="right">{fmt(r.return_pct)}</TableCell>
                            <TableCell align="right">{fmt(r.max_drawdown_pct)}</TableCell>
                          </TableRow>
                        );
                      })}
                    </TableBody>
                  </Table>
                </TableContainer>
              </Box>
            ))
          ) : (
            <TableContainer component={Paper} variant="outlined">
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>策略</TableCell>
                    <TableCell>標的</TableCell>
                    <TableCell>評等</TableCell>
                    <TableCell align="right">回合數</TableCell>
                    <TableCell align="right">勝率%</TableCell>
                    <TableCell align="right">報酬%</TableCell>
                    <TableCell align="right">最大回撤%</TableCell>
                    <TableCell>更新時間</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {fits.map((r) => {
                    const v = VERDICT[r.verdict] || { label: r.verdict, color: "default" };
                    return (
                      <TableRow key={r.id}>
                        <TableCell>{r.strategy_key}</TableCell>
                        <TableCell>{r.symbol}</TableCell>
                        <TableCell>
                          <Chip size="small" color={v.color} label={v.label} />
                        </TableCell>
                        <TableCell align="right">{r.num_round_trips}</TableCell>
                        <TableCell align="right">{fmt(r.win_rate_pct)}</TableCell>
                        <TableCell align="right">{fmt(r.return_pct)}</TableCell>
                        <TableCell align="right">{fmt(r.max_drawdown_pct)}</TableCell>
                        <TableCell>{r.updated_at ? r.updated_at.slice(0, 10) : "—"}</TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </CardContent>
      </Card>

      {/* ── 被汰弱的 Bot ── */}
      <Typography variant="h6" sx={{ mb: 1 }}>
        被汰弱的 Bot
      </Typography>
      <Card variant="outlined">
        <CardContent>
          {culled.length === 0 ? (
            <Typography color="text.secondary">目前沒有被汰弱的 Bot。</Typography>
          ) : (
            <TableContainer component={Paper} variant="outlined">
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Bot</TableCell>
                    <TableCell>策略</TableCell>
                    <TableCell>標的</TableCell>
                    <TableCell>汰弱理由</TableCell>
                    <TableCell>時間</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {culled.map((b) => (
                    <TableRow key={b.id}>
                      <TableCell>{b.name}</TableCell>
                      <TableCell>{b.strategy}</TableCell>
                      <TableCell>{b.symbol}</TableCell>
                      <TableCell sx={{ color: "text.secondary" }}>{b.cull_reason || "—"}</TableCell>
                      <TableCell>{b.culled_at ? b.culled_at.slice(0, 16).replace("T", " ") : "—"}</TableCell>
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
