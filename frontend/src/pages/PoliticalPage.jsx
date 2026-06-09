// ============================================================
// PoliticalPage：政治專討員 / Discord 事件流（/political）
// ============================================================
// Phase 10 step-05：政治專討員從 Discord 偵測政治貼文（例如川普發文鏡像）→ 本機 Ollama
// 判讀 → 落表。這頁純呈現：上方顯示「風險煞車現況」、下方列出判讀過的政治事件。
//
// ★ 定位：**煞車（降風險 / 不開新倉），不是油門（不猜方向）。** 是否真的縮部位由後端
// political_size_factor（預設關）+ 既有 event_risk 決定，這頁只如實顯示、不下單、不改部位。
//
// 設計：沿用既有表格頁風格與深藍主題（吃 theme/NEON，不寫死 hex）。

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
} from "@mui/material";
import { api } from "../api";

// 情緒 label 的中文標籤 + 配色（吃 MUI 語意色）
const LABEL_META = {
  bearish: { label: "偏空（風險）", color: "error" },
  bullish: { label: "偏多", color: "success" },
  neutral: { label: "中性", color: "default" },
};

export default function PoliticalPage() {
  const [rows, setRows] = useState([]);
  const [risk, setRisk] = useState(null);
  const [err, setErr] = useState("");

  const load = useCallback(async () => {
    setErr("");
    try {
      const [events, riskNow] = await Promise.all([
        api.getPoliticalEvents(),
        api.getPoliticalRisk(),
      ]);
      setRows(events);
      setRisk(riskNow);
    } catch (e) {
      setErr(e.message);
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load();
  }, [load]);

  // 風險現況橫幅：brake=不開新倉(紅)、size_factor<1=縮部位(黃)、否則放行(資訊)
  const riskBanner = (() => {
    if (!risk) return null;
    if (risk.brake) {
      return { severity: "error", text: `🚦 政治風險煞車：不開新倉。${risk.reason || ""}` };
    }
    if (risk.size_factor < 1) {
      return {
        severity: "warning",
        text: `🚦 政治風險：縮部位至 ${(risk.size_factor * 100).toFixed(0)}%。${risk.reason || ""}`,
      };
    }
    return { severity: "info", text: `🚦 政治風險閘：放行（不影響下單）。${risk.reason || ""}` };
  })();

  return (
    <Box>
      <Typography variant="h4" sx={{ mb: 1 }}>
        政治專討員
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        從 Discord 偵測政治貼文 → 本機 Ollama 判讀 → 接既有風險煞車。定位是<strong>煞車</strong>
        （重大負面 → 縮部位 / 不開新倉），<strong>不猜方向、不放大部位</strong>。這頁只呈現，不下單。
      </Typography>

      {riskBanner && (
        <Alert severity={riskBanner.severity} sx={{ mb: 2 }}>
          {riskBanner.text}
        </Alert>
      )}

      <Stack direction="row" spacing={2} sx={{ mb: 2 }}>
        <Button size="small" variant="outlined" onClick={load}>
          重新整理
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
              還沒有政治事件。需先有「同步川普貼文的 Discord 頻道」+ 設定 token，並啟動政治專討員 runner。
            </Typography>
          ) : (
            <TableContainer component={Paper} variant="outlined">
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>發文時間</TableCell>
                    <TableCell>作者 / 來源</TableCell>
                    <TableCell>內容摘要</TableCell>
                    <TableCell>判讀</TableCell>
                    <TableCell align="right">分數</TableCell>
                    <TableCell align="right">24h / 1h 發文</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {rows.map((r) => {
                    const meta = LABEL_META[r.label] || { label: r.label, color: "default" };
                    return (
                      <TableRow key={r.id}>
                        <TableCell>
                          {r.posted_at ? r.posted_at.slice(0, 16).replace("T", " ") : "—"}
                        </TableCell>
                        <TableCell>
                          {r.author || "—"}
                          <Typography variant="caption" color="text.secondary" display="block">
                            {r.source}
                          </Typography>
                        </TableCell>
                        <TableCell sx={{ maxWidth: 360, color: "text.secondary" }}>
                          {r.content_summary || "—"}
                          {r.reason ? (
                            <Typography variant="caption" color="text.secondary" display="block">
                              判讀：{r.reason}
                            </Typography>
                          ) : null}
                        </TableCell>
                        <TableCell>
                          <Chip size="small" label={meta.label} color={meta.color} />
                        </TableCell>
                        <TableCell align="right">{r.score}</TableCell>
                        <TableCell align="right">
                          {r.posts_last_24h ?? "—"} / {r.posts_last_1h ?? "—"}
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </CardContent>
      </Card>
    </Box>
  );
}
