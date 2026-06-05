// ============================================================
// ChartGrid：2x2 多視窗 K 線網格（同時盯多檔）
// ============================================================
// 為什麼要網格？一個畫面只看一檔太慢，服役中的 Bot 可能同時跑好幾檔，
// 2x2 讓你一眼掃過四檔的走勢與水位線。
//
// 每一格都是獨立的：自己的股票代號輸入框 + 一張 LightweightChart，
// 並依該檔對應的 Bot 算出自己的水位線（進場/止損/追蹤止盈）。
//
// props:
//   bots：目前所有 Bot（用來幫每一格配對水位線）
//   onPriceLineDrag：拖曳水位線時的回呼（botId, field, pct）→ 存回後端

import { useState } from "react";
import { Box, TextField } from "@mui/material";

import LightweightChart from "../LightweightChart";
import { buildBotPriceLines, findBotForSymbol } from "../utils/priceLines";

// 預設四格股票：先放幾檔常見的，使用者可在每格自行改。
const DEFAULT_SYMBOLS = ["AAPL", "TSLA", "NVDA", "MSFT"];

// 從 Bot 清單挑出「服役中」的股票，優先帶進網格（沒有就用預設）。
function initialSymbols(bots) {
  const active = (bots || [])
    .filter((b) => b.is_active)
    .map((b) => b.symbol);
  // 去重 + 補滿四格
  const uniq = [...new Set([...active, ...DEFAULT_SYMBOLS])];
  return uniq.slice(0, 4);
}

export default function ChartGrid({ bots = [], onPriceLineDrag }) {
  // 四格各自的股票代號（已載入圖表的）與輸入框暫存值
  const [symbols, setSymbols] = useState(() => initialSymbols(bots));
  const [inputs, setInputs] = useState(() => initialSymbols(bots));

  // 在某一格按 Enter → 把該格圖表換成輸入的代號
  function loadCell(i) {
    setSymbols((prev) => {
      const next = [...prev];
      next[i] = (inputs[i] || "").toUpperCase();
      return next;
    });
  }

  return (
    <Box
      sx={{
        display: "grid",
        gridTemplateColumns: "1fr 1fr",
        gridTemplateRows: "1fr 1fr",
        gap: 1.5,
        height: "75vh",
        minHeight: 480,
      }}
    >
      {symbols.map((sym, i) => (
        <Box
          key={i}
          sx={{
            border: "1px solid",
            borderColor: "divider",
            borderRadius: 1,
            p: 1,
            display: "flex",
            flexDirection: "column",
            overflow: "hidden",
          }}
        >
          {/* 每格的代號輸入框（按 Enter 載入） */}
          <TextField
            size="small"
            value={inputs[i]}
            onChange={(e) =>
              setInputs((prev) => {
                const next = [...prev];
                next[i] = e.target.value;
                return next;
              })
            }
            onKeyDown={(e) => {
              if (e.key === "Enter") loadCell(i);
            }}
            placeholder="代號後按 Enter"
            sx={{ mb: 1, width: 160 }}
          />
          {/* 該格圖表 + 自己的水位線 */}
          <Box sx={{ flex: 1, minHeight: 0 }}>
            <LightweightChart
              symbol={sym}
              height="100%"
              priceLines={buildBotPriceLines(findBotForSymbol(bots, sym))}
              onPriceLineDrag={onPriceLineDrag}
            />
          </Box>
        </Box>
      ))}
    </Box>
  );
}
