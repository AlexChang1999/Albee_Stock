// ============================================================
// useLiveQuote：訂閱某股票的即時報價（WebSocket）
// ============================================================
// 用法：
//   const quote = useLiveQuote("AAPL");
//   // quote = { price, prevPrice, ts } 或 null（還沒收到第一筆）
//
// 這個 Hook 負責：
//   1. 跟後端開一條 WebSocket（/ws/quotes）
//   2. 連上後送出「訂閱這檔股票」的指令
//   3. 收到後端推來的價格就更新 state（畫面跟著跳動）
//   4. 斷線時自動重連；元件卸載 / 換股票時退訂並關閉連線
//
// 觀念：WebSocket 跟一般 fetch 不同——它是「連線一直開著、雙向即時傳訊息」，
// 所以特別適合「報價一直跳動」這種需求。

import { useEffect, useState } from "react";

// 後端網址（與 api.js 一致），把 http(s) 換成 ws(s) 才是 WebSocket 的網址。
const BASE_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";
const WS_URL = BASE_URL.replace(/^http/, "ws") + "/ws/quotes";

export function useLiveQuote(symbol) {
  // quote 結構：{ price: 最新價, prevPrice: 上一筆價, ts: 時間戳 }
  const [quote, setQuote] = useState(null);

  useEffect(() => {
    if (!symbol) return;

    let ws;
    let closedByUs = false; // 區分「我們主動關」與「意外斷線」
    let reconnectTimer;

    function connect() {
      ws = new WebSocket(WS_URL);

      // 連上後，告訴後端我們要訂閱這檔股票
      ws.onopen = () => {
        ws.send(JSON.stringify({ action: "subscribe", symbols: [symbol] }));
      };

      // 收到後端推來的價格
      ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        // 只處理「目前這檔股票」的訊息（同一條連線理論上只訂這檔，但保險起見過濾）
        if (msg.symbol === symbol) {
          setQuote((prev) => ({
            price: msg.price,
            // 把上一筆價記下來，畫面才能比較漲跌、決定顏色
            prevPrice: prev ? prev.price : msg.price,
            ts: msg.ts,
          }));
        }
      };

      // 意外斷線 → 2 秒後自動重連（除非是我們自己關的）
      ws.onclose = () => {
        if (!closedByUs) {
          reconnectTimer = setTimeout(connect, 2000);
        }
      };
    }

    connect();

    // 清理函式：元件卸載、或 symbol 改變時會跑。
    return () => {
      closedByUs = true;
      clearTimeout(reconnectTimer);
      if (ws && ws.readyState === WebSocket.OPEN) {
        // 先禮貌退訂，再關連線
        ws.send(JSON.stringify({ action: "unsubscribe", symbols: [symbol] }));
      }
      if (ws) ws.close();
    };
  }, [symbol]); // symbol 一變，就重新訂閱新股票

  return quote;
}
