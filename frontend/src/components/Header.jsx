// ============================================================
// Header：頂部標題列（精緻淺色金融 sticky header）
// ============================================================
// props：
//   status — 交易環境狀態物件 { is_paper, allow_live, live_armed }（可為 null）
//            用來在右側顯示「模擬交易（綠）／⚠️ 實盤·真錢（紅）」標示。
// sticky 讓它捲動時固定在最上方。
//
// 風格：襯線字標（Fraunces）+ 一個黃銅金的菱形標記，安靜高雅，不發光。

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
        px: { xs: 2, md: 5 },
        py: 1.75,
        display: "flex",
        alignItems: "center",
        gap: 1.75,
        // 半透明白 + 輕微模糊：捲動時內容不會直接貼著字標
        background: "rgba(248,246,241,0.82)",
        backdropFilter: "blur(10px)",
        WebkitBackdropFilter: "blur(10px)",
        borderBottom: "1px solid rgba(28,34,48,0.08)",
      }}
    >
      {/* 標記：黃銅金菱形（45° 旋轉的小方塊），低調的品牌記號 */}
      <Box
        sx={{
          width: 12,
          height: 12,
          bgcolor: NEON.magenta,
          transform: "rotate(45deg)",
          borderRadius: "2px",
          boxShadow: "0 1px 4px rgba(176,136,58,0.4)",
        }}
      />
      <Box sx={{ display: "flex", flexDirection: "column" }}>
        <Typography
          sx={{
            fontFamily: '"Fraunces", serif',
            fontWeight: 600,
            fontSize: { xs: 20, md: 25 },
            letterSpacing: "0.02em",
            lineHeight: 1,
            color: "#1c2230",
          }}
        >
          Albee&nbsp;Terminal
        </Typography>
        <Typography
          sx={{
            fontFamily: '"IBM Plex Mono", monospace',
            fontSize: 11,
            letterSpacing: "0.18em",
            color: "rgba(28,34,48,0.5)",
            textTransform: "uppercase",
            mt: 0.4,
          }}
        >
          美股自動交易機器人
        </Typography>
      </Box>

      {/* 交易環境標示：模擬=綠、實盤(真錢)=紅。靠右對齊（ml:auto 推到最右） */}
      {status && (
        <Chip
          size="small"
          variant="outlined"
          color={status.live_armed ? "error" : "success"}
          label={status.live_armed ? "⚠️ 實盤（真錢）" : "模擬交易"}
          sx={{ ml: "auto", fontWeight: 600 }}
        />
      )}
    </Box>
  );
}
