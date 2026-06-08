// ============================================================
// Stat：顯示一個金融數字（標籤 + 數值）
// ============================================================
// 帳戶資訊、回測結果都用到，所以抽成共用小元件。
// 數值用等寬字（JetBrains Mono），金融數字對齊更整齊、更有終端機感。
//
// 顏色吃主題（text.secondary / text.primary）而非寫死——深藍主題下若寫死深色
// 文字會貼在深藍面板上看不見（redesign 換深底後的對比修正）。

import { Box, Typography } from "@mui/material";

export default function Stat({ label, value }) {
  return (
    <Box>
      <Typography
        variant="caption"
        color="text.secondary"
        sx={{
          fontFamily: '"JetBrains Mono", monospace',
          letterSpacing: 1,
          textTransform: "uppercase",
          fontSize: 11,
        }}
      >
        {label}
      </Typography>
      <Typography
        color="text.primary"
        sx={{
          fontFamily: '"JetBrains Mono", monospace',
          fontWeight: 700,
          fontSize: 22,
        }}
      >
        {value}
      </Typography>
    </Box>
  );
}
