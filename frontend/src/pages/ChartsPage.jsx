// ============================================================
// ChartsPage：K 線圖（單一大圖 / 2x2 四格）
// ============================================================
// Phase 9 step-01：原 App tab 2 的內容原樣搬成路由頁，行為不變。
// 圖表元件仍用 React.lazy 延遲載入（內含較重的圖表庫）。

import { lazy, Suspense } from "react";
import {
  Box,
  TextField,
  Button,
  Typography,
  ToggleButton,
  ToggleButtonGroup,
} from "@mui/material";
import { useOutletContext } from "react-router-dom";
import LiveQuote from "../components/LiveQuote";

const LightweightChart = lazy(() => import("../LightweightChart"));
const ChartGrid = lazy(() => import("../components/ChartGrid"));

export default function ChartsPage() {
  const {
    bots,
    chartView,
    setChartView,
    symbolInput,
    setSymbolInput,
    chartSymbol,
    setChartSymbol,
    chartPriceLines,
    onPriceLineDrag,
  } = useOutletContext();

  return (
    <Box>
      {/* 佈局切換：單一大圖 / 2x2 四格 */}
      <Box sx={{ mb: 2 }}>
        <ToggleButtonGroup
          size="small"
          exclusive
          value={chartView}
          onChange={(e, v) => v && setChartView(v)}
        >
          <ToggleButton value="single">單一</ToggleButton>
          <ToggleButton value="grid">2x2 四格</ToggleButton>
        </ToggleButtonGroup>
      </Box>

      {/* Suspense：lazy 圖表元件還在下載時，先顯示 fallback 提示 */}
      <Suspense
        fallback={
          <Box
            sx={{
              height: "75vh",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "text.secondary",
            }}
          >
            圖表載入中…
          </Box>
        }
      >
        {chartView === "grid" ? (
          // ----- 2x2 網格：每格自帶代號輸入與水位線 -----
          <ChartGrid bots={bots} onPriceLineDrag={onPriceLineDrag} />
        ) : (
          // ----- 單一大圖 -----
          <Box>
            <Box sx={{ display: "flex", gap: 1, mb: 2 }}>
              <TextField
                size="small"
                label="股票代號"
                value={symbolInput}
                onChange={(e) => setSymbolInput(e.target.value)}
                placeholder="例如：AAPL、TSLA、NVDA"
              />
              <Button
                variant="contained"
                onClick={() => setChartSymbol(symbolInput.toUpperCase())}
              >
                載入圖表
              </Button>
            </Box>
            {/* 即時報價（WebSocket 推送，價格會即時跳動、依漲跌變色） */}
            <Box sx={{ mb: 2 }}>
              <LiveQuote symbol={chartSymbol} />
            </Box>
            {/* 可拖拉調整大小的圖表容器（拉右下角） */}
            <Box
              sx={{
                resize: "vertical",
                overflow: "hidden",
                height: "75vh",
                minHeight: 320,
                border: "1px solid",
                borderColor: "divider",
                borderRadius: 1,
              }}
            >
              <LightweightChart
                symbol={chartSymbol}
                height="100%"
                priceLines={chartPriceLines}
                onPriceLineDrag={onPriceLineDrag}
              />
            </Box>
            <Typography variant="caption" color="text.secondary">
              提示：拖曳圖表框的右下角可調整高度。
            </Typography>
          </Box>
        )}
      </Suspense>
    </Box>
  );
}
