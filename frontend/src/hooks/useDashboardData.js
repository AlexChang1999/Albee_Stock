// ============================================================
// useDashboardData：把「載入儀表板資料」這件事打包成一個自訂 Hook
// ============================================================
// 什麼是 custom hook？
//   就是一個名字以 use 開頭、內部會用到其他 hook（useState/useEffect）的
//   普通函式。它讓我們把「一組相關的狀態 + 邏輯」從元件裡搬出來重複使用，
//   元件因此變乾淨——只管畫面，不管資料怎麼來。
//
// 這個 hook 負責：
//   - 持有 account / bots / trades 三份資料的 state
//   - 第一次掛載時自動載入一次
//   - 對外提供 reload()，讓「建立／刪除／啟停 Bot」之後能重新抓最新資料
//   - 用 loading 表示「正在抓資料」，用 loadError 表示「抓失敗」
//
// 用法（在元件裡）：
//   const { account, bots, trades, loading, loadError, reload } =
//     useDashboardData();

import { useState, useEffect, useCallback } from "react";
import { api } from "../api";

export function useDashboardData() {
  const [account, setAccount] = useState(null);
  const [status, setStatus] = useState(null); // 交易環境狀態（模擬／實盤）
  const [bots, setBots] = useState([]);
  const [trades, setTrades] = useState([]);
  const [loading, setLoading] = useState(true); // 第一次載入預設為 true
  const [loadError, setLoadError] = useState("");

  // reload：重新向後端抓所有資料。
  // 用 useCallback 包起來，讓這個函式的「身分」在多次 render 之間保持穩定，
  // 這樣下面 useEffect 的相依陣列 [reload] 才不會每次 render 都觸發。
  const reload = useCallback(async () => {
    setLoading(true);
    setLoadError("");
    try {
      // 交易環境狀態：拿不到不致命（後端沒開時下面帳戶錯誤已會提示），靜默略過
      setStatus(await api.getStatus());
    } catch {
      /* 略過 */
    }
    try {
      setAccount(await api.getAccount());
    } catch (e) {
      setLoadError(
        "無法取得帳戶資料（後端有啟動嗎？API 金鑰正確嗎？）：" + e.message
      );
    }
    try {
      setBots(await api.getBots());
      setTrades(await api.getTrades());
    } catch (e) {
      setLoadError(e.message);
    } finally {
      setLoading(false); // 不論成功失敗都結束載入
    }
  }, []);

  // 元件第一次出現在畫面上時，自動載入一次。
  //
  // 關於下面這行 eslint-disable：
  //   React 19 新增的 set-state-in-effect 規則會提醒「不要在 effect 裡同步呼叫
  //   setState」，因為那常代表你其實該在事件處理或 render 階段算值。
  //   但「掛載時去後端抓資料」正是 effect 的正當用途（跟外部系統同步），
  //   reload() 內第一行 setLoading(true) 會被規則視為同步 setState 而誤報。
  //   這裡確認是刻意為之，故只在這一行關閉該規則。
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    reload();
  }, [reload]);

  return { account, status, bots, trades, loading, loadError, reload };
}
