// ============================================================
// LightweightChart：原生 K 線圖元件（取代 TradingView iframe）
// ============================================================
// 為什麼換掉 TradingView widget？
//   iframe 是「別人的視窗」，React 沒辦法在上面畫我們自己算的水位線
//   （進場均價 / 止損 / 追蹤止盈）。改用 lightweight-charts 後，
//   K 線資料與水平線都由我們的程式控制，要畫哪條線就畫哪條。
//
// 用法：
//   <LightweightChart symbol="AAPL" height={500} priceLines={[...]} />
//
// 資料來源：
//   - 歷史蠟燭：後端 GET /bars/{symbol}（api.getBars）
//   - 即時跳動：useLiveQuote(symbol)（WebSocket 推來最新價，更新最後一根 K 棒）
//
// priceLines（選填）：水位線陣列，每筆 { price, color, title, dashed }
//   交由父元件（App）依 Bot 風控資料算好再傳進來，本元件只負責畫。

import { useEffect, useRef } from "react";
import { createChart, CandlestickSeries, LineStyle } from "lightweight-charts";

import { api } from "./api";
import { useLiveQuote } from "./hooks/useLiveQuote";

export default function LightweightChart({
  symbol = "AAPL",
  height = 500,
  priceLines = [],
}) {
  const containerRef = useRef(null); // 圖表掛載的 <div>
  const chartRef = useRef(null); // chart 實例
  const seriesRef = useRef(null); // 蠟燭 series 實例
  const lastBarRef = useRef(null); // 最後一根 K 棒（即時報價要更新它）
  const priceLineRefs = useRef([]); // 已畫上去的水位線物件，方便之後清掉

  // 即時報價（WebSocket）。symbol 換了會自動重新訂閱。
  const quote = useLiveQuote(symbol);

  // ---------- 1. 建立圖表（只在掛載時做一次）----------
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const chart = createChart(container, {
      width: container.clientWidth,
      height: container.clientHeight || height,
      layout: { background: { color: "transparent" }, textColor: "#333" },
      grid: {
        vertLines: { color: "rgba(0,0,0,0.05)" },
        horzLines: { color: "rgba(0,0,0,0.05)" },
      },
      timeScale: { timeVisible: false, borderColor: "rgba(0,0,0,0.1)" },
      rightPriceScale: { borderColor: "rgba(0,0,0,0.1)" },
    });

    // v5 寫法：addSeries(型別, 選項)。漲綠跌紅。
    const series = chart.addSeries(CandlestickSeries, {
      upColor: "#1f7a5a",
      downColor: "#b23b32",
      borderUpColor: "#1f7a5a",
      borderDownColor: "#b23b32",
      wickUpColor: "#1f7a5a",
      wickDownColor: "#b23b32",
    });

    chartRef.current = chart;
    seriesRef.current = series;

    // 容器大小改變時（拖曳調整高度 / 視窗縮放），讓圖表跟著縮放
    const ro = new ResizeObserver(() => {
      chart.applyOptions({
        width: container.clientWidth,
        height: container.clientHeight || height,
      });
    });
    ro.observe(container);

    // 清理：元件卸載時拆掉圖表與監聽，避免記憶體洩漏
    return () => {
      ro.disconnect();
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
      lastBarRef.current = null;
      priceLineRefs.current = [];
    };
  }, [height]);

  // ---------- 2. 載入歷史蠟燭（symbol 改變時重抓）----------
  useEffect(() => {
    let cancelled = false;
    const series = seriesRef.current;
    if (!series || !symbol) return;

    api
      .getBars(symbol)
      .then((res) => {
        if (cancelled) return;
        const candles = res.candles || [];
        series.setData(candles);
        lastBarRef.current = candles.length ? candles[candles.length - 1] : null;
        chartRef.current?.timeScale().fitContent();
      })
      .catch(() => {
        // 抓不到資料（離線 / 代號錯）就清空，不讓整個畫面崩
        if (!cancelled) series.setData([]);
      });

    return () => {
      cancelled = true;
    };
  }, [symbol]);

  // ---------- 3. 即時報價：更新最後一根 K 棒 ----------
  useEffect(() => {
    const series = seriesRef.current;
    const last = lastBarRef.current;
    if (!series || !last || !quote?.price) return;

    // 用最新價更新「當天這根」蠟燭的收盤；順手刷新最高/最低
    const updated = {
      ...last,
      close: quote.price,
      high: Math.max(last.high, quote.price),
      low: Math.min(last.low, quote.price),
    };
    series.update(updated);
    lastBarRef.current = updated;
  }, [quote]);

  // ---------- 4. 水位線（priceLines 改變時重畫）----------
  useEffect(() => {
    const series = seriesRef.current;
    if (!series) return;

    // 先清掉舊線
    priceLineRefs.current.forEach((line) => series.removePriceLine(line));
    priceLineRefs.current = [];

    // 再依最新的 priceLines 畫上去
    (priceLines || []).forEach((pl) => {
      if (pl?.price == null) return;
      const line = series.createPriceLine({
        price: pl.price,
        color: pl.color || "#888",
        lineWidth: 2,
        lineStyle: pl.dashed ? LineStyle.Dashed : LineStyle.Solid,
        axisLabelVisible: true,
        title: pl.title || "",
      });
      priceLineRefs.current.push(line);
    });
  }, [priceLines]);

  return <div ref={containerRef} style={{ width: "100%", height }} />;
}
