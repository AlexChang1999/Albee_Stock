// ============================================================
// KnowledgeCard：策略知識卡（知識庫 / 進化實驗室共用）
// ============================================================
// Phase 9 step-07：呈現一筆 StrategyKnowledge（Phase 8）的理論/場景/使用時機/
// OOS 指標/狀態親和性。供 LibraryPage（唯讀）與 EvolutionPage（含審核按鈕）共用。
// 前端只顯示後端結果，不重算 EV/驗證。
//
// props：
//   item     — 一筆知識（_dict 結構）
//   actions  — 右下動作區（晉升/退回等按鈕），由呼叫端傳入；唯讀頁不傳

import { Paper, Box, Typography, Chip, Stack, Divider } from "@mui/material";
import { NEON } from "../theme";

// status → 中文標籤 + 配色
const STATUS_META = {
  candidate: { label: "候選", color: "default" },
  validated: { label: "已驗證", color: "primary" },
  curated: { label: "策展庫", color: "secondary" },
  rejected: { label: "已退回", color: "error" },
};

export default function KnowledgeCard({ item, actions }) {
  const oos = item.oos_metrics || {};
  const ev = oos.expected_value;
  const bestRegime = item.regime_affinity?.best_regime;
  const status = STATUS_META[item.status] || { label: item.status, color: "default" };

  return (
    <Paper variant="outlined" sx={{ p: 1.5, height: "100%", display: "flex", flexDirection: "column" }}>
      <Stack direction="row" alignItems="center" justifyContent="space-between">
        <Typography variant="subtitle2" noWrap sx={{ minWidth: 0 }}>
          {item.name}
        </Typography>
        <Chip size="small" color={status.color} label={status.label} />
      </Stack>
      <Typography variant="caption" color="text.secondary">
        {item.strategy_key}
      </Typography>

      {item.theory && (
        <Typography variant="body2" sx={{ mt: 1 }}>
          <strong>理論：</strong>
          {item.theory}
        </Typography>
      )}
      {item.scenario && (
        <Typography variant="body2" sx={{ mt: 0.5 }}>
          <strong>場景：</strong>
          {item.scenario}
        </Typography>
      )}
      {item.usage_note && (
        <Typography variant="body2" sx={{ mt: 0.5 }}>
          <strong>使用時機：</strong>
          {item.usage_note}
        </Typography>
      )}

      <Box sx={{ flexGrow: 1 }} />

      <Divider sx={{ my: 1 }} />
      <Stack direction="row" flexWrap="wrap" gap={0.5}>
        <Chip
          size="small"
          label={`OOS EV ${ev ?? "—"}`}
          sx={{ color: (ev ?? 0) >= 0 ? NEON.green : NEON.red }}
        />
        {oos.win_rate_pct != null && (
          <Chip size="small" label={`勝率 ${oos.win_rate_pct}%`} />
        )}
        {bestRegime && <Chip size="small" label={`最適狀態：${bestRegime}`} />}
      </Stack>

      {actions && <Box sx={{ mt: 1 }}>{actions}</Box>}
    </Paper>
  );
}
