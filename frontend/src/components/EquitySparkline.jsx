// ============================================================
// EquitySparkline：資金曲線迷你圖（純 SVG，不引新圖表庫）
// ============================================================
// Phase 9 step-03：回測歷史頁要在不開完整報表的情況下，快速瞄一眼資金曲線走勢。
// equity_curve 是一串數字（每根的總資產），這裡用純 SVG 折線畫成 sparkline，
// 末端高於起點＝綠（賺）、否則紅（賠）。不引 lightweight-charts（殺雞用牛刀）。
//
// props：
//   data   — number[]（資金曲線）
//   width  — px（預設 240）
//   height — px（預設 56）

import { Box, Typography } from "@mui/material";
import { NEON } from "../theme";

export default function EquitySparkline({ data, width = 240, height = 56 }) {
  if (!Array.isArray(data) || data.length < 2) {
    return (
      <Typography variant="caption" color="text.secondary">
        無足夠資金曲線資料
      </Typography>
    );
  }

  const min = Math.min(...data);
  const max = Math.max(...data);
  const span = max - min || 1; // 全平時避免除以 0
  const stepX = width / (data.length - 1);

  // 把每個點映射到 SVG 座標（y 軸上下顛倒：值越大越靠上）
  const points = data
    .map((v, i) => {
      const x = i * stepX;
      const y = height - ((v - min) / span) * height;
      return `${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(" ");

  const up = data[data.length - 1] >= data[0];
  const color = up ? NEON.green : NEON.red;

  return (
    <Box sx={{ my: 1 }}>
      <svg width={width} height={height} style={{ display: "block" }}>
        <polyline
          points={points}
          fill="none"
          stroke={color}
          strokeWidth="1.5"
          strokeLinejoin="round"
          strokeLinecap="round"
        />
      </svg>
    </Box>
  );
}
