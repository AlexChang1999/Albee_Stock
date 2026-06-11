// ============================================================
// LightweightChart：原生 K 線圖元件（取代 TradingView iframe）
// ============================================================
// 為什麼換掉 TradingView widget？
//   iframe 是「別人的視窗」，React 沒辦法在上面畫我們自己算的水位線
//   （進場均價 / 止損 / 追蹤止盈）。改用 lightweight-charts 後，
//   K 線資料與水平線都由我們的程式控制，要畫哪條線就畫哪條。
//
// 用法：
//   <LightweightChart symbol="AAPL" height={500} priceLines={[...]}
//                     onPriceLineDrag={(botId, field, pct) => ...} />
//
// 資料來源：
//   - 歷史蠟燭：後端 GET /bars/{symbol}（api.getBars）
//   - 即時跳動：useLiveQuote(symbol)（WebSocket 推來最新價，更新最後一根 K 棒）
//
// priceLines（選填）：水位線陣列，每筆 { price, color, title, dashed,
//   editable?, botId?, field?, refPrice? }。交由父元件（App）依 Bot 風控資料算好。
//
// 拖曳（editable 線才有）：lightweight-charts 的水平線原生「不能拖」，
//   所以我們在圖右側自己疊一個可拖的把手 DOM，對齊到線的 y 座標：
//   - 用 series.priceToCoordinate(價) 把「價格」換成「畫面 y 像素」→ 擺把手
//   - 拖動時用 series.coordinateToPrice(y) 反推新價格，即時移動線
//   - 放開時把新價格換算成百分比，呼叫 onPriceLineDrag 通知父元件存回後端

import { useEffect, useMemo, useRef, useState } from "react";
import {
  createChart,
  createSeriesMarkers,
  CandlestickSeries,
  LineSeries,
  LineStyle,
} from "lightweight-charts";

import { api } from "./api";
import { useLiveQuote } from "./hooks/useLiveQuote";
import { priceToPct } from "./utils/priceLines";

export default function LightweightChart({
  symbol = "AAPL",
  height = 500,
  priceLines = [],
  onPriceLineDrag,
  // ----- 策略可視化（Stage 4）三個選用 props：不傳 = 行為與舊版完全一致 -----
  candles = null, // 外部餵 K 線（/bots/{id}/chart-data 回的）；null = 自己抓 /bars
  markers = null, // 買賣/決策標記（已轉成 lightweight-charts marker 格式、依時間排序）
  overlays = null, // 主圖疊線 [{ id, title, color(hex), data: [{time,value}] }]
  pane = null, // 振盪器副圖 { title, series: [...同上], levels: [數值參考線] }
}) {
  const containerRef = useRef(null); // 圖表掛載的 <div>
  const chartRef = useRef(null); // chart 實例
  const seriesRef = useRef(null); // 蠟燭 series 實例
  const lastBarRef = useRef(null); // 最後一根 K 棒（即時報價要更新它）
  const priceLineRefs = useRef([]); // 已畫上去的水位線物件，方便之後清掉
  const markersPluginRef = useRef(null); // v5 marker plugin（買賣標記）
  const overlaySeriesRef = useRef([]); // 主圖疊線 series（換 Bot 時要清掉重畫）
  const paneSeriesRef = useRef([]); // 副圖 series（同上）

  // 拖曳用：每條可編輯線對應的「線物件 + 中繼資料 + 目前價格」，順序與下面的
  // editableLines 一致。把手 DOM、目前價格都用 ref 存，拖曳時直接改 DOM/物件，
  // 不觸發 React 重繪（每幀重繪會很卡）。
  const editableObjsRef = useRef([]); // [{ obj, meta }]
  const currentPricesRef = useRef([]); // 每條可編輯線的目前價格（拖曳會即時改）
  const handleNodesRef = useRef([]); // 每個把手的 DOM 節點
  const draggingRef = useRef(null); // 正在拖第幾條（null = 沒在拖）
  const rafRef = useRef(0);

  // 載入狀態：loading（抓資料中）/ ok（有資料）/ empty（查無資料）/ error（抓取失敗）
  // 用來在 canvas 上疊一層提示，避免「空白畫布」讓人以為當機（圖表規則 §10）。
  const [status, setStatus] = useState("loading");

  // 即時報價（WebSocket）。symbol 換了會自動重新訂閱。
  const quote = useLiveQuote(symbol);

  // 只有可編輯（editable）的線才需要把手。用 useMemo 避免每次 render 重算。
  const editableLines = useMemo(
    () => (priceLines || []).filter((l) => l?.editable && l.price != null),
    [priceLines]
  );

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
    // v5 的買賣標記改成 plugin 形式（不是 v4 的 series.setMarkers）：掛載時建一次
    markersPluginRef.current = createSeriesMarkers(series, []);

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
      editableObjsRef.current = [];
      markersPluginRef.current = null;
      overlaySeriesRef.current = [];
      paneSeriesRef.current = [];
    };
  }, [height]);

  // ---------- 2. 載入歷史蠟燭（symbol 改變時重抓；外部餵 candles 時直接用）----------
  useEffect(() => {
    let cancelled = false;
    const series = seriesRef.current;
    if (!series) return;

    // 外部餵資料模式（策略視角圖：candles 來自 /bots/{id}/chart-data，
    // 與指標同一份 df 算出，保證時間軸對齊）→ 不自己抓 /bars
    if (candles) {
      series.setData(candles);
      lastBarRef.current = candles.length ? candles[candles.length - 1] : null;
      chartRef.current?.timeScale().fitContent();
      setStatus(candles.length ? "ok" : "empty");
      return;
    }
    if (!symbol) return;

    setStatus("loading");
    api
      .getBars(symbol)
      .then((res) => {
        if (cancelled) return;
        const candles = res.candles || [];
        series.setData(candles);
        lastBarRef.current = candles.length ? candles[candles.length - 1] : null;
        chartRef.current?.timeScale().fitContent();
        setStatus(candles.length ? "ok" : "empty");
      })
      .catch(() => {
        // 抓不到資料（離線 / 代號錯）就清空，不讓整個畫面崩
        if (!cancelled) {
          series.setData([]);
          setStatus("error");
        }
      });

    return () => {
      cancelled = true;
    };
  }, [symbol, candles]);

  // ---------- 2b. 買賣/決策標記（markers 改變時重設）----------
  useEffect(() => {
    markersPluginRef.current?.setMarkers(markers || []);
  }, [markers]);

  // ---------- 2c. 主圖指標疊線（overlays 改變時清舊畫新）----------
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    overlaySeriesRef.current.forEach((s) => {
      try {
        chart.removeSeries(s);
      } catch {
        // series 已隨 chart 卸載 → 略過
      }
    });
    overlaySeriesRef.current = [];
    (overlays || []).forEach((ov) => {
      // paneIndex 0 = 主圖（與 K 線同軸）
      const s = chart.addSeries(
        LineSeries,
        {
          color: ov.color,
          lineWidth: 1,
          priceLineVisible: false,
          lastValueVisible: false,
          title: ov.title || "",
        },
        0
      );
      s.setData(ov.data || []);
      overlaySeriesRef.current.push(s);
    });
  }, [overlays]);

  // ---------- 2d. 振盪器副圖（pane 改變時清舊畫新）----------
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    paneSeriesRef.current.forEach((s) => {
      try {
        chart.removeSeries(s);
      } catch {
        // series 已隨 chart 卸載 → 略過
      }
    });
    paneSeriesRef.current = [];
    if (!pane || !pane.series?.length) return;

    pane.series.forEach((ln, i) => {
      // paneIndex 1 = 第一次 addSeries 會自動建出副圖區
      const s = chart.addSeries(
        LineSeries,
        {
          color: ln.color,
          lineWidth: 1,
          priceLineVisible: false,
          lastValueVisible: true,
          title: ln.title || "",
        },
        1
      );
      s.setData(ln.data || []);
      // 水平參考線（超買/超賣/零軸）掛在第一條 series 上即可
      if (i === 0) {
        (pane.levels || []).forEach((lvl) => {
          s.createPriceLine({
            price: lvl,
            color: "rgba(154,169,194,0.5)",
            lineWidth: 1,
            lineStyle: LineStyle.Dashed,
            axisLabelVisible: true,
            title: "",
          });
        });
      }
      paneSeriesRef.current.push(s);
    });

    // 副圖高度調成主圖的約 1/3（API 不存在時靜默略過，不影響畫圖）
    try {
      const panes = chart.panes();
      if (panes[1]?.setStretchFactor) {
        panes[0].setStretchFactor(3);
        panes[1].setStretchFactor(1);
      }
    } catch {
      // 版本差異 → 用預設比例
    }
  }, [pane]);

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
    editableObjsRef.current = [];

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
      // 可編輯的線：記下線物件 + 中繼資料，順序與 editableLines 相同
      if (pl.editable) editableObjsRef.current.push({ obj: line, meta: pl });
    });

    // 把手的目前價格重置成最新的線價格
    currentPricesRef.current = editableLines.map((l) => l.price);
  }, [priceLines, editableLines]);

  // ---------- 5. 把手位置同步（rAF）----------
  // 圖表平移/縮放/自動縮放時，價格對應的 y 像素會一直變。每幀把把手 DOM
  // 對齊到線目前價格的 y 座標，讓把手「黏」在線上。沒有可編輯線就不跑。
  useEffect(() => {
    if (editableLines.length === 0) return;

    const tick = () => {
      const series = seriesRef.current;
      if (series) {
        currentPricesRef.current.forEach((price, i) => {
          const node = handleNodesRef.current[i];
          if (!node || price == null) return;
          const y = series.priceToCoordinate(price);
          if (y == null) {
            node.style.display = "none"; // 線目前不在可見範圍內 → 藏把手
          } else {
            node.style.display = "flex";
            node.style.top = `${y}px`;
          }
        });
      }
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);

    return () => cancelAnimationFrame(rafRef.current);
  }, [editableLines.length]);

  // ---------- 6. 拖曳把手 ----------
  function handlePointerDown(index, e) {
    e.preventDefault();
    draggingRef.current = index;

    const onMove = (ev) => {
      const i = draggingRef.current;
      const series = seriesRef.current;
      const container = containerRef.current;
      if (i == null || !series || !container) return;

      const rect = container.getBoundingClientRect();
      const y = ev.clientY - rect.top; // 滑鼠在圖內的 y 像素
      const price = series.coordinateToPrice(y);
      if (price == null || price <= 0) return;

      currentPricesRef.current[i] = price;
      // 即時移動那條線（rAF 會把把手跟著移到新位置）
      editableObjsRef.current[i]?.obj?.applyOptions({ price });
    };

    const onUp = () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);

      const i = draggingRef.current;
      draggingRef.current = null;
      if (i == null) return;

      const meta = editableLines[i];
      const newPrice = currentPricesRef.current[i];
      // 反推百分比：止損/追蹤止盈都是「低於參考價的比例」= 1 − 新價/參考價
      const pct = priceToPct(meta?.refPrice, newPrice);
      if (pct != null && meta?.botId != null && onPriceLineDrag) {
        onPriceLineDrag(meta.botId, meta.field, pct);
      }
    };

    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
  }

  return (
    <div style={{ position: "relative", width: "100%", height }}>
      <div ref={containerRef} style={{ width: "100%", height: "100%" }} />

      {/* 載入/空資料/錯誤的覆蓋提示（status 非 ok 才顯示）。pointerEvents:none
          讓有資料後不擋圖表互動；無資料時也不會是一片空白讓人誤以為當機。 */}
      {status !== "ok" && (
        <div
          style={{
            position: "absolute",
            inset: 0,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            pointerEvents: "none",
            color: "#9aa9c2",
            fontSize: 14,
            fontFamily: "var(--font-body)",
            textAlign: "center",
            padding: "0 16px",
          }}
        >
          {status === "loading"
            ? "圖表載入中…"
            : status === "empty"
            ? "查無資料（請確認股票代號）"
            : "資料載入失敗，請稍後再試"}
        </div>
      )}

      {/* 可拖曳把手：疊在圖右側，y 由 rAF 對齊到線；拖它即可調整止損/止盈 */}
      {editableLines.map((line, i) => (
        <div
          key={`${line.botId}-${line.field}`}
          ref={(el) => (handleNodesRef.current[i] = el)}
          onPointerDown={(e) => handlePointerDown(i, e)}
          title={`拖曳調整${line.title}`}
          style={{
            position: "absolute",
            right: 56, // 避開右側價格軸
            transform: "translateY(-50%)",
            display: "none", // rAF 算出位置後才顯示
            alignItems: "center",
            gap: 4,
            padding: "1px 6px",
            fontSize: 11,
            lineHeight: 1.6,
            color: "#fff",
            background: line.color || "#888",
            borderRadius: 4,
            cursor: "ns-resize",
            userSelect: "none",
            touchAction: "none",
            zIndex: 3,
            boxShadow: "0 1px 4px rgba(0,0,0,0.4)",
          }}
        >
          ⇅ {line.title}
        </div>
      ))}
    </div>
  );
}
