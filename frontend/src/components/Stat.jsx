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
          // 用主題語意色（深色面板上才看得清；原本寫死的深色 hex 是 light-theme 殘留）
          color: "text.secondary",
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
          color: "text.primary",
          fontVariantNumeric: "tabular-nums", // 數字等寬，多列對齊不跳動
        }}
      >
        {value}
      </Typography>
    </Box>
  );
}
