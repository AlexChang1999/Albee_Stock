// ============================================================
// Header：頂部標題列（霓虹玻璃 sticky header）
// ============================================================
// props：
//   status — 交易環境狀態物件 { is_paper, allow_live, live_armed }（可為 null）
//            用來在右側顯示「模擬交易（綠）／⚠️ 實盤·真錢（紅）」標示。
// sticky 讓它捲動時固定在最上方。

import { Box, Typography, Chip } from "@mui/material";
import { NEON } from "../theme";

export default function Header({ status }) {
  return (
    <Box
      component="header"
      sx={{
        position: "sticky",
        top: 0,
        zIndex: 10,
        px: { xs: 2, md: 4 },
        py: 1.5,
        display: "flex",
        alignItems: "center",
        gap: 1.5,
        background: "rgba(16,24,48,0.72)",
        backdropFilter: "blur(18px)",
        borderBottom: "1px solid rgba(34,211,238,0.18)",
      }}
    >
      {/* 發光圓點 logo：用 keyframes 做緩慢呼吸脈動 */}
      <Box
        sx={{
          width: 12,
          height: 12,
          borderRadius: "50%",
          bgcolor: NEON.cyan,
          boxShadow: `0 0 12px ${NEON.cyan}`,
          "@keyframes pulse": {
            "0%,100%": { opacity: 1, transform: "scale(1)" },
            "50%": { opacity: 0.4, transform: "scale(0.8)" },
          },
          animation: "pulse 2.4s ease-in-out infinite",
        }}
      />
      <Box sx={{ display: "flex", flexDirection: "column" }}>
        <Typography
          sx={{
            fontFamily: '"Sora", sans-serif',
            fontWeight: 800,
            fontSize: { xs: 18, md: 22 },
            letterSpacing: 1,
            lineHeight: 1,
            // 青→洋紅漸層文字
            background: `linear-gradient(90deg, ${NEON.cyan}, ${NEON.magenta})`,
            WebkitBackgroundClip: "text",
            WebkitTextFillColor: "transparent",
          }}
        >
          ALBEE TERMINAL
        </Typography>
        <Typography
          sx={{
            fontFamily: '"JetBrains Mono", monospace',
            fontSize: 11,
            letterSpacing: 2,
            color: "rgba(232,236,248,0.5)",
            textTransform: "uppercase",
          }}
        >
          美股自動交易機器人
        </Typography>
      </Box>

      {/* 交易環境標示：模擬=綠、實盤(真錢)=紅。靠右對齊（ml:auto 推到最右） */}
      {status && (
        <Chip
          size="small"
          color={status.live_armed ? "error" : "success"}
          label={status.live_armed ? "⚠️ 實盤（真錢）" : "模擬交易"}
          sx={{ ml: "auto", fontWeight: 700 }}
        />
      )}
    </Box>
  );
}
