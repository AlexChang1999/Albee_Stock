// ============================================================
// CollectorPage：市場蒐集員 / 靈感收件匣（/collector）
// ============================================================
// Phase 10 step-04：爬蟲從 RSS / 部落格收回來的「策略描述文字」原料落收件匣，
// 在這頁消化（看過 → 標記狀態）。**這頁只策展，不爬網、不寫策略碼、不建 Bot、不上真錢**——
// 收回來的點子要走 strategy-builder + OOS 閘 + 人工核准才可能上線（一律來自後端）。
//
// 設計：沿用既有表格頁風格（FactorsPage / TradesPage）與深藍主題（吃 theme/NEON）。

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
  Link,
} from "@mui/material";
import { Link as RouterLink } from "react-router-dom";
import { api } from "../api";

// status 的中文標籤 + 配色（吃 MUI 語意色，不寫死 hex）
const STATUS_META = {
  new: { label: "新收", color: "info" },
  triaged: { label: "待試", color: "warning" },
  built: { label: "已寫成策略", color: "success" },
  discarded: { label: "丟棄", color: "default" },
};

// 每個狀態能往哪些狀態流轉（給按鈕用）
const NEXT_ACTIONS = {
  new: ["triaged", "discarded"],
  triaged: ["built", "discarded"],
  built: ["discarded"],
  discarded: ["triaged"],
};

export default function CollectorPage() {
  const [statusFilter, setStatusFilter] = useState("");
  const [rows, setRows] = useState([]);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [busyId, setBusyId] = useState(null); // 哪一筆正在試轉策略

  const load = useCallback(async () => {
    setErr("");
    try {
      setRows(await api.getCollectorFinds({ status: statusFilter || undefined }));
    } catch (e) {
      setErr(e.message);
    }
  }, [statusFilter]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 標記某筆素材的新狀態，成功後重抓清單
  async function setStatus(id, status) {
    setErr("");
    try {
      await api.updateCollectorFind(id, status);
      load();
    } catch (e) {
      setErr(e.message);
    }
  }

  // 對單筆素材即時試轉策略（探勘橋）：成功→建候選並翻 built；不相關→discarded。
  async function triage(id) {
    setErr("");
    setMsg("");
    setBusyId(id);
    try {
      const r = await api.triageFind(id);
      if (r.status === "built") {
        setMsg(`#${id} 已轉成策略候選（knowledge #${r.knowledge_id}）：${r.note}`);
      } else if (r.status === "discarded") {
        setMsg(`#${id} 探勘橋判定與既有策略無關，已丟棄：${r.note}`);
      } else {
        setMsg(`#${id} 暫時無法轉換（${r.note}）。確認本機 Ollama 已啟動再試。`);
      }
      load();
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusyId(null);
    }
  }

  return (
    <Box>
      <Typography variant="h4" sx={{ mb: 1 }}>
        市場蒐集員
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        爬蟲收「策略描述文字」進收件匣。按 <strong>🔬 試轉策略</strong> 讓<strong>探勘橋</strong>用本機 LLM
        把文字判讀成<strong>既有</strong>策略＋參數候選——防唬爛：只能從現有策略清單挑、參數名鎖 schema、
        值夾回合法範圍、信心不足直接丟棄、<strong>不生成新程式碼</strong>。轉出的候選仍要過 OOS 驗證＋人工晉升
        才算數，這頁不下單、不上線。
      </Typography>

      <Stack direction="row" spacing={2} alignItems="center" sx={{ mb: 2 }}>
        <TextField
          select
          size="small"
          label="狀態篩選"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          SelectProps={{ native: true }}
          sx={{ width: 180 }}
        >
          <option value="">全部</option>
          <option value="new">新收</option>
          <option value="triaged">待試</option>
          <option value="built">已寫成策略</option>
          <option value="discarded">丟棄</option>
        </TextField>
        <Button size="small" variant="outlined" onClick={load}>
          查詢
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

      <Card variant="outlined">
        <CardContent>
          {rows.length === 0 ? (
            <Typography color="text.secondary">
              收件匣還沒有素材。設定 COLLECTOR_RSS_FEEDS 並開啟常駐收料後會自動累積。
            </Typography>
          ) : (
            <TableContainer component={Paper} variant="outlined">
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>標題 / 來源</TableCell>
                    <TableCell>摘要</TableCell>
                    <TableCell>收到時間</TableCell>
                    <TableCell>狀態</TableCell>
                    <TableCell>探勘橋</TableCell>
                    <TableCell align="right">策展</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {rows.map((r) => {
                    const meta = STATUS_META[r.status] || { label: r.status, color: "default" };
                    return (
                      <TableRow key={r.id}>
                        <TableCell sx={{ maxWidth: 280 }}>
                          <Link href={r.source_url} target="_blank" rel="noopener" underline="hover">
                            {r.title || r.source_url}
                          </Link>
                          <Typography variant="caption" color="text.secondary" display="block">
                            {r.source}
                          </Typography>
                        </TableCell>
                        <TableCell sx={{ maxWidth: 360, color: "text.secondary" }}>
                          {r.summary || "—"}
                        </TableCell>
                        <TableCell>{r.fetched_at ? r.fetched_at.slice(0, 16).replace("T", " ") : "—"}</TableCell>
                        <TableCell>
                          <Chip size="small" label={meta.label} color={meta.color} />
                        </TableCell>
                        <TableCell sx={{ maxWidth: 260, color: "text.secondary" }}>
                          <Typography variant="caption" display="block">
                            {r.triage_note || "—"}
                          </Typography>
                          {r.knowledge_id && (
                            <Link
                              component={RouterLink}
                              to="/evolution"
                              underline="hover"
                              variant="caption"
                            >
                              → 候選 #{r.knowledge_id}
                            </Link>
                          )}
                        </TableCell>
                        <TableCell align="right">
                          <Stack direction="row" spacing={0.5} justifyContent="flex-end">
                            {["new", "triaged"].includes(r.status) && (
                              <Button
                                size="small"
                                variant="outlined"
                                disabled={busyId === r.id}
                                onClick={() => triage(r.id)}
                              >
                                {busyId === r.id ? "轉換中…" : "🔬 試轉策略"}
                              </Button>
                            )}
                            {(NEXT_ACTIONS[r.status] || []).map((next) => (
                              <Button
                                key={next}
                                size="small"
                                variant="text"
                                onClick={() => setStatus(r.id, next)}
                              >
                                {STATUS_META[next]?.label || next}
                              </Button>
                            ))}
                          </Stack>
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
