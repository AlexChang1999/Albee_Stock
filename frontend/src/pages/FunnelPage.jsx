// ============================================================
// FunnelPage：探勘漏斗全貌（/funnel）
// ============================================================
// Phase 14：把「收料 → 候選 → 驗證 → 入庫」兩條流水線的每個階段數量畫出來，
// 點任一階段就列出該階段的實際項目 + 淘汰理由——直接回答使用者的疑問
// 「蒐集很多、只有幾個晉升，其餘去哪了」（答案：卡在某關或被 OOS 閘淘汰，都留有理由）。
//
// 純呈現：只讀後端既有端點（/company/overview 計數 + /collector/finds + /knowledge），
// 不重算 EV/驗證。顏色吃 MUI 語意色，不寫死 hex。

import { useState, useEffect, useCallback } from "react";
import {
  Box,
  Typography,
  Card,
  CardContent,
  Stack,
  Chip,
  Alert,
  Grid,
  Table,
  TableHead,
  TableBody,
  TableRow,
  TableCell,
  TableContainer,
  Paper,
  Link,
} from "@mui/material";
import { Link as RouterLink } from "react-router-dom";
import { api } from "../api";
import KnowledgeCard from "../components/KnowledgeCard";

// 階段定義：[status 鍵, 中文標籤, MUI 語意色]
const RAW_STAGES = [
  ["new", "新收", "info"],
  ["triaged", "待試", "warning"],
  ["built", "已建候選", "success"],
  ["discarded", "丟棄", "default"],
];
const KNOW_STAGES = [
  ["candidate", "候選", "default"],
  ["validated", "已驗證", "primary"],
  ["curated", "策展庫", "secondary"],
  ["rejected", "已退回", "error"],
];

// 一排可點的階段 chip（顯示數量；選中的填滿）。宣告在元件外，避免每次 render 重建。
function StageRow({ kind, stages, counts, sel, onOpen }) {
  return (
    <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
      {stages.map(([key, label, color]) => {
        const n = counts?.[key] ?? 0;
        const active = sel?.kind === kind && sel?.status === key;
        return (
          <Chip
            key={key}
            label={`${label} ${n}`}
            color={color}
            variant={active ? "filled" : "outlined"}
            onClick={() => onOpen(kind, key)}
            sx={{ cursor: "pointer" }}
          />
        );
      })}
    </Stack>
  );
}

export default function FunnelPage() {
  const [funnel, setFunnel] = useState(null);
  const [err, setErr] = useState("");
  const [sel, setSel] = useState(null); // {kind: "raw"|"knowledge", status}
  const [items, setItems] = useState([]);
  const [loadingItems, setLoadingItems] = useState(false);

  const loadCounts = useCallback(async () => {
    setErr("");
    try {
      const o = await api.getCompanyOverview();
      setFunnel(o.discovery_funnel);
    } catch (e) {
      setErr(e.message);
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadCounts();
  }, [loadCounts]);

  // 點某階段：抓該階段實際項目（raw 走收件匣端點、knowledge 走知識端點）。
  const openStage = useCallback(async (kind, status) => {
    setSel({ kind, status });
    setLoadingItems(true);
    setItems([]);
    try {
      const rows =
        kind === "raw"
          ? await api.getCollectorFinds({ status, limit: 200 })
          : await api.getKnowledge(status);
      setItems(rows);
    } catch (e) {
      setErr(e.message);
    } finally {
      setLoadingItems(false);
    }
  }, []);

  const selLabel =
    sel &&
    (sel.kind === "raw" ? RAW_STAGES : KNOW_STAGES).find((s) => s[0] === sel.status)?.[1];

  return (
    <Box>
      <Typography variant="h4" sx={{ mb: 1 }}>
        探勘漏斗
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        蒐集很多、只有幾個晉升——其餘沒消失，是卡在某一關或被 OOS 閘淘汰（都留有理由）。
        點任一階段看實際項目與淘汰理由。流水線靠「公司戰情 · 操作台」逐關手動推進。
      </Typography>

      {err && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setErr("")}>
          {err}
        </Alert>
      )}

      {!funnel ? (
        <Typography color="text.secondary">載入中…</Typography>
      ) : (
        <Grid container spacing={2} sx={{ mb: 2 }}>
          <Grid item xs={12} md={6}>
            <Card variant="outlined">
              <CardContent>
                <Typography variant="h6" sx={{ mb: 1 }}>
                  收件匣流水線（raw）
                </Typography>
                <StageRow kind="raw" stages={RAW_STAGES} counts={funnel.raw} sel={sel} onOpen={openStage} />
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} md={6}>
            <Card variant="outlined">
              <CardContent>
                <Typography variant="h6" sx={{ mb: 1 }}>
                  知識庫流水線
                </Typography>
                <StageRow kind="knowledge" stages={KNOW_STAGES} counts={funnel.knowledge} sel={sel} onOpen={openStage} />
                <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 1 }}>
                  淘汰率 {funnel.rejection_rate_pct ?? "—"}
                  {funnel.rejection_rate_pct != null && "%"}
                  （高是健康的：多數點子過不了 OOS 閘是預期）
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      {/* 選定階段的明細 */}
      {sel && (
        <Card variant="outlined">
          <CardContent>
            <Typography variant="h6" sx={{ mb: 1 }}>
              {sel.kind === "raw" ? "收件匣" : "知識庫"}：{selLabel}（{items.length}）
            </Typography>
            {loadingItems ? (
              <Typography color="text.secondary">載入中…</Typography>
            ) : items.length === 0 ? (
              <Typography color="text.secondary">這一階段沒有項目。</Typography>
            ) : sel.kind === "knowledge" ? (
              <Grid container spacing={2}>
                {items.map((it) => (
                  <Grid item xs={12} sm={6} md={4} key={it.id}>
                    <KnowledgeCard item={it} />
                  </Grid>
                ))}
              </Grid>
            ) : (
              <TableContainer component={Paper} variant="outlined">
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>標題 / 來源</TableCell>
                      <TableCell>探勘橋決策</TableCell>
                      <TableCell>對應候選</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {items.map((r) => (
                      <TableRow key={r.id}>
                        <TableCell sx={{ maxWidth: 320 }}>
                          <Link href={r.source_url} target="_blank" rel="noopener" underline="hover">
                            {r.title || r.source_url}
                          </Link>
                          <Typography variant="caption" color="text.secondary" display="block">
                            {r.source}
                          </Typography>
                        </TableCell>
                        <TableCell sx={{ maxWidth: 320, color: "text.secondary" }}>
                          {r.triage_note || "—"}
                        </TableCell>
                        <TableCell>
                          {r.knowledge_id ? (
                            <Link component={RouterLink} to="/evolution" underline="hover">
                              候選 #{r.knowledge_id}
                            </Link>
                          ) : (
                            "—"
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            )}
          </CardContent>
        </Card>
      )}
    </Box>
  );
}
