// ============================================================
// LibraryPage：策略知識庫（/library）
// ============================================================
// Phase 9 step-07：Phase 8 知識庫的唯讀策展庫 + 排行呈現。
//   理論 / 場景 / 使用時機 / OOS 指標 / 狀態親和性，依 OOS EV 排序。
// 唯讀：不做晉升/退回（那在 /evolution）；前端不重算 EV。

import { useState, useEffect, useCallback } from "react";
import {
  Box,
  Typography,
  ToggleButton,
  ToggleButtonGroup,
  Grid,
  Alert,
} from "@mui/material";
import { api } from "../api";
import KnowledgeCard from "../components/KnowledgeCard";

export default function LibraryPage() {
  // 看哪一層：策展庫（curated）或已驗證（validated）
  const [status, setStatus] = useState("curated");
  const [items, setItems] = useState([]);
  const [err, setErr] = useState("");

  const load = useCallback(async () => {
    setErr("");
    try {
      // 排行端點已依 OOS EV 由高到低排序
      setItems(await api.getKnowledgeRanking(status));
    } catch (e) {
      setErr(e.message);
    }
  }, [status]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load();
  }, [load]);

  return (
    <Box>
      <Typography variant="h4" sx={{ mb: 2 }}>
        策略知識庫
      </Typography>

      <ToggleButtonGroup
        size="small"
        exclusive
        value={status}
        onChange={(e, v) => v && setStatus(v)}
        sx={{ mb: 2 }}
      >
        <ToggleButton value="curated">策展庫</ToggleButton>
        <ToggleButton value="validated">已驗證</ToggleButton>
      </ToggleButtonGroup>

      {err && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setErr("")}>
          {err}
        </Alert>
      )}

      <Grid container spacing={2}>
        {items.length === 0 && (
          <Grid item xs={12}>
            <Typography variant="caption" color="text.secondary">
              這一層還沒有策略。到「進化實驗室」驗證候選、晉升後會出現在策展庫。
            </Typography>
          </Grid>
        )}
        {items.map((item) => (
          <Grid item xs={12} sm={6} md={4} key={item.id}>
            <KnowledgeCard item={item} />
          </Grid>
        ))}
      </Grid>
    </Box>
  );
}
