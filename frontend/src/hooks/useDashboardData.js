// ============================================================
// useDashboardData：把「載入儀表板資料」這件事打包成一個自訂 Hook
// ============================================================
// 什麼是 custom hook？
//   就是一個名字以 use 開頭、內部會用到其他 hook（useState/useEffect）的
//   普通函式。它讓我們把「一組相關的狀態 + 邏輯」從元件裡搬出來重複使用，
//   元件因此變乾淨——只管畫面，不管資料怎麼來。
//
// 這個 hook 負責：
//   - 持有 account / status / bots / trades 的 state
//   - 第一次掛載時自動載入一次
//   - 背景每 POLL_MS 靜默輪詢一次（不閃進度條），讓 Bot 動態自動更新；
//     分頁切到背景時暫停輪詢、切回前景時立即刷新一次
//   - 對外提供 reload()，讓「建立／刪除／啟停 Bot」之後能重新抓最新資料
//   - 用 loading 表示「正在抓資料」，用 loadError 表示「抓失敗」
//
// 用法（在元件裡）：
//   const { account, status, bots, trades, loading, loadError, reload } =
//     useDashboardData();

import { useState, useEffect, useCallback, useRef } from "react";
import { api } from "../api";

// 背景輪詢間隔（毫秒）。30 秒夠即時又不會打爆後端。
const POLL_MS = 30000;

export function useDashboardData() {
  const [account, setAccount] = useState(null);
  const [status, setStatus] = useState(null); // 交易環境狀態（模擬／實盤）
  const [bots, setBots] = useState([]);
  const [trades, setTrades] = useState([]);
  const [loading, setLoading] = useState(true); // 第一次載入預設為 true
  const [loadError, setLoadError] = useState("");

  // 卸載守衛：元件卸載後不要再 setState（避免背景輪詢的非同步回來時報錯）。
  const mountedRef = useRef(true);
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  // reload：重新向後端抓所有資料。
  //   silent=true（背景輪詢用）時不動 loading，避免每 30 秒閃一次頂部進度條。
  // 用 useCallback 包起來，讓函式身分在多次 render 間穩定，下面 effect 的
  // 相依陣列 [reload] 才不會每次 render 都重跑。
  const reload = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    setLoadError("");
    try {
      // 交易環境狀態：拿不到不致命（後端沒開時下面帳戶錯誤已會提示），靜默略過
      const st = await api.getStatus();
      if (mountedRef.current) setStatus(st);
    } catch {
      /* 略過 */
    }
    try {
      const acc = await api.getAccount();
      if (mountedRef.current) setAccount(acc);
    } catch (e) {
      if (mountedRef.current)
        setLoadError(
          "無法取得帳戶資料（後端有啟動嗎？API 金鑰正確嗎？）：" + e.message
        );
    }
    try {
      // bots / trades 互不相依 → 平行抓，較快
      const [b, t] = await Promise.all([api.getBots(), api.getTrades()]);
      if (mountedRef.current) {
        setBots(b);
        setTrades(t);
      }
    } catch (e) {
      if (mountedRef.current) setLoadError(e.message);
    } finally {
      if (!silent && mountedRef.current) setLoading(false);
    }
  }, []);

  // 元件第一次出現在畫面上時，自動載入一次。
  //
  // 關於下面這行 eslint-disable：
  //   React 19 新增的 set-state-in-effect 規則會提醒「不要在 effect 裡同步呼叫
  //   setState」，但「掛載時去後端抓資料」正是 effect 的正當用途（跟外部系統同步），
  //   reload() 內 setLoading(true) 會被規則視為同步 setState 而誤報。
  //   這裡確認是刻意為之，故只在這一行關閉該規則。
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    reload();
  }, [reload]);

  // 背景輪詢：每 POLL_MS 靜默刷新一次（分頁在背景時不抓）；
  // 分頁從背景切回前景時，立即刷新一次（不必等下一個間隔）。
  useEffect(() => {
    const timer = setInterval(() => {
      if (!document.hidden) reload(true);
    }, POLL_MS);
    const onVisible = () => {
      if (!document.hidden) reload(true);
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [reload]);

  return { account, status, bots, trades, loading, loadError, reload };
}
