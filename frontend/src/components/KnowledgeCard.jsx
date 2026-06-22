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

// 從 oos_metrics 還原「這筆是怎麼驗來的」出處（防止只看一個 EV 數字、不知怎麼來）。
// 單檔 → {symbol, walk_forward[], single_split}；籃子 → {symbols[], per_symbol[]}；
// 零交易 → {noop}。欄位缺就略過，空字串代表沒有可顯示的出處。
function describeProvenance(oos) {
  if (!oos || typeof oos !== "object") return "";
  let scope = "";
  if (Array.isArray(oos.symbols)) scope = `籃子 ${oos.symbols.length} 檔`;
  else if (oos.symbol) scope = `單檔 ${oos.symbol}`;

  if (oos.noop) return [scope, `no-op：${oos.noop.reason}`].filter(Boolean).join("｜");

  let folds = "";
  if (Array.isArray(oos.walk_forward)) folds = `${oos.walk_forward.length} 個 walk-forward fold`;
  else if (Array.isArray(oos.per_symbol)) {
    const q = oos.per_symbol.filter((s) => s.qualified).length;
    folds = `${q}/${oos.per_symbol.length} 檔達標池化`;
  }
  const days = oos.days ? `回看 ${oos.days} 天` : "";
  return [scope, folds, days].filter(Boolean).join("｜");
}

export default function KnowledgeCard({ item, actions }) {
  const oos = item.oos_metrics || {};
  const ev = oos.expected_value;
  // 勝率在 oos_metrics 裡藏在 single_split（單檔驗證才有）；籃子驗證沒有單一勝率。
  const winRate = oos.single_split?.win_rate_pct ?? oos.win_rate_pct;
  const provenance = describeProvenance(oos);
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
        {winRate != null && (
          <Chip size="small" label={`勝率 ${winRate}%`} />
        )}
        {bestRegime && <Chip size="small" label={`最適狀態：${bestRegime}`} />}
      </Stack>

      {/* 出處：這筆是怎麼驗來的（驗證標的範圍 / 折數 / 回看天數），不是只有一個 EV 數字 */}
      {provenance && (
        <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5 }}>
          出處：{provenance}
        </Typography>
      )}

      {actions && <Box sx={{ mt: 1 }}>{actions}</Box>}
    </Paper>
  );
}
