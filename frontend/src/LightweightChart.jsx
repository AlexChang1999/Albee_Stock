// ============================================================
// 原生 K 線圖元件（lightweight-charts v5）
// ============================================================
// 取代原本的 TradingView <iframe> widget。
//
// 為什麼換掉 TradingView：
//   TradingView widget 是「別人的視窗」，React 無法在上面畫線。
//   改用 lightweight-charts 後，K 線資料由我們後端 /bars 供應，
//   就能把後端算出的「進場價／止損／止盈」水位線疊在圖上（見 priceLines）。
//
// 使用方式：
//   <LightweightChart symbol="AAPL" source="alpaca" priceLines={[...]} />
//
// lightweight-charts v5 的 API 跟舊版 v4 不一樣：
//   v4：chart.addCandlestickSeries({...})
//   v5：chart.addSeries(CandlestickSeries, {...})   ← 本檔用這個

import { useEffect, useRef, useState } from "react";
import { createChart, CandlestickSeries } from "lightweight-charts";

import { api } from "./api";

// 漲跌配色（先用通用綠紅；未來深藍主題會改成青綠／洋紅）
const UP_COLOR = "#26a69a"; // 漲：青綠
const DOWN_COLOR = "#ef5350"; // 跌：洋紅紅

export default function LightweightChart({
  symbol = "AAPL",
  source = "alpaca",
  days = 120,
  height = 500,
  priceLines = [], // [{ price, color, title, lineStyle }]，水位線（進場/止損…）
}) {
  const containerRef = useRef(null); // 圖表掛載的 <div>
  const chartRef = useRef(null); // chart 實例（跨 effect 共用）
  const seriesRef = useRef(null); // K 線 series 實例
  const priceLineRefs = useRef([]); // 已建立的水位線，方便重畫前清掉

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // ---- 1. 建立圖表（只在元件掛載時做一次）----
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const chart = createChart(container, {
      autoSize: true, // 自動填滿容器（取代手動算寬高）
      layout: {
        background: { color: "transparent" },
        textColor: "#9aa0a6",
      },
      grid: {
        vertLines: { color: "rgba(255,255,255,0.06)" },
        horzLines: { color: "rgba(255,255,255,0.06)" },
      },
      timeScale: { timeVisible: false, borderColor: "rgba(255,255,255,0.12)" },
      rightPriceScale: { borderColor: "rgba(255,255,255,0.12)" },
      crosshair: { mode: 0 }, // 0 = 自由十字線（不吸附）
    });

    // v5：用 addSeries(CandlestickSeries, options) 建蠟燭圖
    const series = chart.addSeries(CandlestickSeries, {
      upColor: UP_COLOR,
      downColor: DOWN_COLOR,
      borderUpColor: UP_COLOR,
      borderDownColor: DOWN_COLOR,
      wickUpColor: UP_COLOR,
      wickDownColor: DOWN_COLOR,
    });

    chartRef.current = chart;
    seriesRef.current = series;

    // 元件卸載時銷毀圖表，避免記憶體洩漏
    return () => {
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, []);

  // ---- 2. 抓 K 線資料（symbol / source / days 改變時重抓）----
  useEffect(() => {
    let cancelled = false; // 防止 race：舊請求晚回來蓋掉新資料
    setLoading(true);
    setError("");

    api
      .getBars(symbol, days, source)
      .then((res) => {
        if (cancelled) return;
        const series = seriesRef.current;
        if (!series) return;
        series.setData(res.bars || []);
        chartRef.current?.timeScale().fitContent(); // 自動縮放到看得到全部
        setLoading(false);
      })
      .catch((e) => {
        if (cancelled) return;
        setError(e.message || "讀取 K 線失敗");
        setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [symbol, source, days]);

  // ---- 3. 畫水位線（priceLines 改變時重畫）----
  useEffect(() => {
    const series = seriesRef.current;
    if (!series) return;

    // 先清掉上一輪的線
    priceLineRefs.current.forEach((line) => series.removePriceLine(line));
    priceLineRefs.current = [];

    // 重新建立目前要顯示的水位線
    priceLines.forEach((pl) => {
      if (pl.price == null || Number.isNaN(pl.price)) return;
      const line = series.createPriceLine({
        price: pl.price,
        color: pl.color || "#888",
        lineWidth: 2,
        lineStyle: pl.lineStyle ?? 0, // 0 實線 / 2 虛線
        axisLabelVisible: true,
        title: pl.title || "",
      });
      priceLineRefs.current.push(line);
    });
  }, [priceLines]);

  return (
    <div style={{ position: "relative", height, width: "100%" }}>
      <div ref={containerRef} style={{ height: "100%", width: "100%" }} />

      {/* 載入／錯誤的浮層提示 */}
      {(loading || error) && (
        <div
          style={{
            position: "absolute",
            inset: 0,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: error ? "#ef5350" : "#9aa0a6",
            pointerEvents: "none",
            fontSize: 14,
          }}
        >
          {error ? `⚠ ${error}` : "K 線載入中…"}
        </div>
      )}
    </div>
  );
}
