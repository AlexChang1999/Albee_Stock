// ============================================================
// TradingView 即時線圖元件
// ============================================================
// 使用 TradingView 免費的「Advanced Chart Widget」。
// 做法：動態建立一個 <script>，把設定(JSON)塞進去，
//       TradingView 的程式就會把互動式線圖畫到這個容器裡。
//
// 使用方式：<TradingViewChart symbol="AAPL" />

import { useEffect, useRef } from "react";

export default function TradingViewChart({ symbol = "AAPL", height = 500 }) {
  // useRef：拿到畫面上那個 <div> 的參照，等下把圖表塞進去
  const containerRef = useRef(null);

  // useEffect：當 symbol 改變時，重新建立圖表
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    // 先清空（避免 symbol 切換時殘留舊圖）
    container.innerHTML = "";

    // TradingView 實際渲染的目標 div
    const widgetDiv = document.createElement("div");
    widgetDiv.className = "tradingview-widget-container__widget";
    widgetDiv.style.height = "100%";
    widgetDiv.style.width = "100%";
    container.appendChild(widgetDiv);

    // 建立 TradingView 的官方嵌入腳本
    const script = document.createElement("script");
    script.src =
      "https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js";
    script.type = "text/javascript";
    script.async = true;

    // 圖表設定（這段 JSON 就是 widget 的參數）
    script.innerHTML = JSON.stringify({
      autosize: true, // 自動填滿容器
      symbol: symbol, // 股票代號，例如 "AAPL"
      interval: "D", // 預設週期：日線
      timezone: "Asia/Taipei",
      theme: "light",
      style: "1", // 1 = 蠟燭圖
      locale: "zh_TW", // 介面用繁體中文
      allow_symbol_change: true, // 允許在圖上自己換股票
      hide_side_toolbar: false, // 顯示左側畫圖工具
      support_host: "https://www.tradingview.com",
    });

    container.appendChild(script);
  }, [symbol]);

  return (
    <div
      className="tradingview-widget-container"
      ref={containerRef}
      style={{ height, width: "100%" }}
    />
  );
}
