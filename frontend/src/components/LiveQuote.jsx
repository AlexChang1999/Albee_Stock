// ============================================================
// LiveQuote：即時報價顯示元件
// ============================================================
// 顯示某檔股票的即時價格，並依漲/跌變色（綠/紅）、價格更新時閃一下。
// 資料來源是 useLiveQuote Hook（WebSocket 推送）。

import { Box, Typography, Chip } from "@mui/material";
import { useLiveQuote } from "../hooks/useLiveQuote";
import { quoteDirection, formatPrice } from "../utils/quote";

export default function LiveQuote({ symbol }) {
  const quote = useLiveQuote(symbol);

  // 還沒收到第一筆推送
  const price = quote ? quote.price : null;
  const dir = quote ? quoteDirection(quote.price, quote.prevPrice) : "flat";

  // 依漲跌方向決定顏色
  const color =
    dir === "up" ? "success.main" : dir === "down" ? "error.main" : "text.secondary";
  const arrow = dir === "up" ? "▲" : dir === "down" ? "▼" : "";

  return (
    <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
      <Chip label={symbol} size="small" />
      <Typography
        variant="h6"
        sx={{
          color,
          fontVariantNumeric: "tabular-nums", // 數字等寬，跳動時不會左右抖
          transition: "color 0.2s",
        }}
      >
        {arrow} ${formatPrice(price)}
      </Typography>
      <Typography variant="caption" color="text.secondary">
        {quote ? "即時" : "等待報價…"}
      </Typography>
    </Box>
  );
}
