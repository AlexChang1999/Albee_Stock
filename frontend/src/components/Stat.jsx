// ============================================================
// Stat：顯示一個金融數字（標籤 + 數值）
// ============================================================
// 帳戶資訊、回測結果都用到，所以抽成共用小元件。
// 數值用等寬字（JetBrains Mono），金融數字對齊更整齊、更有終端機感。

import { Box, Typography } from "@mui/material";

export default function Stat({ label, value }) {
  return (
    <Box>
      <Typography
        variant="caption"
        sx={{
          color: "rgba(232,236,248,0.5)",
          fontFamily: '"JetBrains Mono", monospace',
          letterSpacing: 1,
          textTransform: "uppercase",
          fontSize: 11,
        }}
      >
        {label}
      </Typography>
      <Typography
        sx={{
          fontFamily: '"JetBrains Mono", monospace',
          fontWeight: 700,
          fontSize: 22,
          color: "#e8ecf8",
        }}
      >
        {value}
      </Typography>
    </Box>
  );
}
