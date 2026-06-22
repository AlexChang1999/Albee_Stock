// ============================================================
// BotActivityStatus：Bot 卡片上的「即時活動條」
// ============================================================
// 顯示這個 Bot 此刻在幹嘛——抓數據（脈衝點）、計算/風控（掃光條）、
// 決策結果（閃現 chip）、待機倒數（下輪 Xs）、失聯警示（紅框明滅）、
// 休市待機（靜態灰 chip）。
//
// 鐵則：動畫 100% 由 useBotActivity 的真事件驅動，這裡只負責「畫」。
// WS 沒連上（activity 為空）→ 渲染 null，卡片回到原本的輪詢顯示（優雅降級）。
//
// 顏色一律由 theme 的 NEON 色票推導（深底主題勿寫死淺色 hex）。

import { Box, Chip, Typography, GlobalStyles } from "@mui/material";
import { alpha } from "@mui/material/styles";
import { useEffect, useState } from "react";
import { NEON } from "../theme";
import { actionMeta } from "../utils/decisionMeta";

// CSS keyframes 全域定義一次（BotList 渲染 <ActivityKeyframes /> 即可，
// 不要在每張卡片各塞一份 <GlobalStyles>）
export function ActivityKeyframes() {
  return (
    <GlobalStyles
      styles={{
        // 抓數據：圓點脈衝（亮藍冷光擴散）
        "@keyframes bot-pulse": {
          "0%": { boxShadow: `0 0 0 0 ${alpha(NEON.cyan, 0.5)}` },
          "100%": { boxShadow: `0 0 0 10px ${alpha(NEON.cyan, 0)}` },
        },
        // 計算/風控：背景漸層掃光（亮藍 → 黃金）
        "@keyframes bot-compute": {
          "0%": { backgroundPosition: "200% 0" },
          "100%": { backgroundPosition: "-200% 0" },
        },
        // 決策結果：chip 閃現（縮放 + 淡入）
        "@keyframes decision-flash": {
          from: { transform: "scale(0.85)", opacity: 0 },
          to: { transform: "scale(1)", opacity: 1 },
        },
        // 失聯警示：紅框緩慢明滅
        "@keyframes stale-blink": {
          "0%, 100%": { opacity: 1 },
          "50%": { opacity: 0.45 },
        },
        // 決策流新列滑入（DecisionFeed 共用）
        "@keyframes feed-slide-in": {
          from: { transform: "translateY(-8px)", opacity: 0 },
          to: { transform: "translateY(0)", opacity: 1 },
        },
      }}
    />
  );
}

// 進行中階段的呈現設定：點色 + 是否掃光
const PHASE_RUNNING = {
  cycle_start: { color: NEON.cyan, sweep: false },
  fetch_data: { color: NEON.cyan, sweep: false },
  compute_signal: { color: NEON.magenta, sweep: true },
  risk_check: { color: NEON.magenta, sweep: true },
  order_submitted: { color: NEON.green, sweep: false },
};

/** 待機倒數：每秒重算剩餘秒數（只在這顆小元件內重繪，不打擾整張卡）。 */
function Countdown({ nextRunAt }) {
  const [, force] = useState(0);
  useEffect(() => {
    const t = setInterval(() => force((n) => n + 1), 1000);
    return () => clearInterval(t);
  }, []);
  const remain = Math.max(0, Math.ceil((nextRunAt - Date.now()) / 1000));
  return (
    <Typography variant="caption" color="text.secondary">
      下輪 {remain}s
    </Typography>
  );
}

export default function BotActivityStatus({ activity }) {
  // WS 沒連上 / 還沒收過這顆 Bot 的事件 → 不顯示（卡片維持原本輪詢資訊）
  if (!activity) return null;

  const { phase, detail, decision, nextRunAt, marketClosed, stale } = activity;

  // --- 失聯警示（真跑/假跑偵測器）：最高優先 ---
  if (stale) {
    return (
      <Box sx={{ minHeight: 28, display: "flex", alignItems: "center", gap: 1 }}>
        <Chip
          size="small"
          variant="outlined"
          label="⚠ 排程未回應"
          sx={{
            color: NEON.red,
            borderColor: NEON.red,
            animation: "stale-blink 1.2s ease-in-out infinite",
          }}
        />
      </Box>
    );
  }

  // --- 休市待機：靜態顯示，不閃動畫 ---
  if (phase === "idle" && marketClosed) {
    return (
      <Box sx={{ minHeight: 28, display: "flex", alignItems: "center", gap: 1 }}>
        <Chip size="small" variant="outlined" label="休市待機" sx={{ color: "text.secondary" }} />
        {nextRunAt && <Countdown nextRunAt={nextRunAt} />}
      </Box>
    );
  }

  // --- 待機倒數：顯示最近決策 + 下輪倒數 ---
  if (phase === "idle") {
    const meta = decision ? actionMeta(decision.action) : null;
    return (
      <Box sx={{ minHeight: 28, display: "flex", alignItems: "center", gap: 1 }}>
        {meta && (
          <Chip
            size="small"
            variant="outlined"
            label={meta.label}
            sx={{ color: meta.color, borderColor: meta.color }}
          />
        )}
        {nextRunAt && <Countdown nextRunAt={nextRunAt} />}
      </Box>
    );
  }

  // --- 決策結果：chip 閃現 + 原因 ---
  if (phase === "decision" && decision) {
    const meta = actionMeta(decision.action);
    return (
      <Box sx={{ minHeight: 28, display: "flex", alignItems: "center", gap: 1, maxWidth: "100%" }}>
        <Chip
          size="small"
          label={meta.label}
          sx={{
            color: meta.color,
            borderColor: meta.color,
            animation: "decision-flash 0.25s ease-out",
          }}
          variant="outlined"
        />
        <Typography variant="caption" color="text.secondary" noWrap title={decision.reason}>
          {decision.reason}
        </Typography>
      </Box>
    );
  }

  // --- 進行中階段：脈衝點（+ 計算/風控時的掃光底）---
  const cfg = PHASE_RUNNING[phase] || PHASE_RUNNING.cycle_start;
  return (
    <Box
      sx={{
        minHeight: 28,
        display: "flex",
        alignItems: "center",
        gap: 1,
        px: 0.75,
        borderRadius: 1,
        maxWidth: "100%",
        ...(cfg.sweep && {
          background: `linear-gradient(90deg, transparent, ${alpha(NEON.cyan, 0.12)}, ${alpha(NEON.magenta, 0.12)}, transparent)`,
          backgroundSize: "200% 100%",
          animation: "bot-compute 1.6s linear infinite",
        }),
      }}
    >
      <Box
        sx={{
          width: 8,
          height: 8,
          borderRadius: "50%",
          flexShrink: 0,
          bgcolor: cfg.color,
          animation: "bot-pulse 1s ease-out infinite",
        }}
      />
      <Typography variant="caption" color="text.secondary" noWrap title={detail}>
        {detail || "執行中…"}
      </Typography>
    </Box>
  );
}
