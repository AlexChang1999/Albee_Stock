// ============================================================
// useBotActivity：訂閱所有 Bot 的即時活動事件（WebSocket）
// ============================================================
// 用法（放在 Dashboard 一處即可，結果往下傳）：
//   const { connected, activityByBot, feed } = useBotActivity();
//   // activityByBot[botId] = { phase, detail, decision, nextRunAt, marketClosed, stale }
//   // feed = 最近 N 則決策事件（最新在前，給即時決策流用）
//
// 設計重點——「資料 100% 真事件、播放節奏前端控」：
//   Bot 一輪執行不到 1 秒，後端會在極短時間內連發 5~8 則事件。
//   直接照收照播人眼根本看不到，所以每個 Bot 維護一條「播放佇列」：
//   事件照順序進佇列，每則至少顯示 PHASE_MIN_MS 才換下一則。
//   動畫呈現的內容全部來自真事件，只有「停留時間」是前端排的。
//
// 真跑/假跑偵測器：
//   cycle_end 事件帶 next_run_in_sec（排程下一輪間隔）。倒數歸零後再寬限
//   STALE_GRACE_MS 還沒等到新一輪 cycle_start → stale=true，卡片亮紅警示。
//   後端掛了/排程死了，前端一定看得到。

import { useEffect, useRef, useState } from "react";

const BASE_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";
const WS_URL = BASE_URL.replace(/^http/, "ws") + "/ws/bot-activity";

// 播放節奏常數（資料是真的，這裡只控制「看得見」）
export const PHASE_MIN_MS = 600;      // 每階段最少顯示時間
export const DECISION_MIN_MS = 1800;  // 決策結果停久一點（這是重點資訊）
export const STALE_GRACE_MS = 15000;  // 倒數歸零後的寬限，吸收排程抖動
const QUEUE_CAP = 20;                 // 佇列上限（手動連點「執行一次」防爆）
const FEED_MAX = 50;                  // 決策流保留則數
const TICK_MS = 200;                  // 播放器推進頻率
const REPLAY_FRESH_SEC = 10;          // 超過這秒數的回放事件不播動畫（只播種狀態）

/** 內部：取得（必要時初始化）某 Bot 的播放狀態。 */
function botSlot(map, botId) {
  if (!map[botId]) {
    map[botId] = {
      queue: [],      // 待播事件
      current: null,  // 播放中的事件
      shownAt: 0,     // current 開始顯示的時刻
      meta: {},       // 待機資訊：nextRunAt / marketClosed / lastDecision
    };
  }
  return map[botId];
}

/** 內部：把一則事件設為「播放中」，並更新待機資訊。 */
function applyEvent(slot, ev, now) {
  slot.current = ev;
  slot.shownAt = now;
  if (ev.phase === "decision" && ev.decision) {
    slot.meta.lastDecision = ev.decision;
  }
  if (ev.phase === "cycle_end") {
    slot.meta.nextRunAt = ev._nextRunAt ?? null;
    slot.meta.marketClosed = ev.status === "skipped_market_closed";
  }
}

/** 內部：算出某 Bot 對外公開的狀態（元件直接吃這個物件渲染）。 */
function publicState(slot, now) {
  if (slot.current) {
    return {
      phase: slot.current.phase,
      detail: slot.current.detail || "",
      decision: slot.current.decision || slot.meta.lastDecision || null,
      nextRunAt: null,
      marketClosed: false,
      stale: false,
    };
  }
  const nextRunAt = slot.meta.nextRunAt || null;
  return {
    phase: "idle",
    detail: "",
    decision: slot.meta.lastDecision || null,
    nextRunAt,
    marketClosed: !!slot.meta.marketClosed,
    // 倒數歸零 + 寬限過了還沒有新一輪 → 排程可疑（真跑/假跑偵測器亮燈）
    stale: !!(nextRunAt && now > nextRunAt + STALE_GRACE_MS),
  };
}

export function useBotActivity() {
  const [connected, setConnected] = useState(false);
  const [activityByBot, setActivityByBot] = useState({});
  const [feed, setFeed] = useState([]);
  const slotsRef = useRef({});       // botId → 播放狀態（不觸發重繪的工作區）
  const lastSnapshotRef = useRef(""); // 上次公開狀態的序列化（變了才 setState）

  useEffect(() => {
    let ws;
    let closedByUs = false;
    let reconnectTimer;

    function handleEvent(msg) {
      const now = Date.now();
      // 回放的舊事件（重連/剛開頁）只拿來播種狀態，不播動畫——動畫必須對應「現在」
      const isFresh = !msg.ts || now / 1000 - msg.ts < REPLAY_FRESH_SEC;

      // 決策事件一律進 feed（含觀望/跳過；用 bot_id+ts 去重，重連回放不會重複）
      if (msg.phase === "decision") {
        const key = `${msg.bot_id}-${msg.ts}`;
        setFeed((prev) =>
          prev.some((e) => `${e.bot_id}-${e.ts}` === key)
            ? prev
            : [msg, ...prev].slice(0, FEED_MAX)
        );
      }

      const slot = botSlot(slotsRef.current, msg.bot_id);

      // cycle_end 先換算「下一輪該到的時刻」（以事件時間為準，回放也算得對）
      if (msg.phase === "cycle_end" && msg.next_run_in_sec) {
        const baseMs = msg.ts ? msg.ts * 1000 : now;
        msg._nextRunAt = baseMs + msg.next_run_in_sec * 1000;
      }

      if (!isFresh) {
        // 舊事件：直接更新待機資訊，跳過播放
        if (msg.phase === "decision" && msg.decision) slot.meta.lastDecision = msg.decision;
        if (msg.phase === "cycle_end") {
          slot.meta.nextRunAt = msg._nextRunAt ?? null;
          slot.meta.marketClosed = msg.status === "skipped_market_closed";
        }
        return;
      }

      // 休市輪：不播動畫（不然休市時卡片整天閃），直接進靜態待機
      if (msg.phase === "cycle_end" && msg.status === "skipped_market_closed") {
        slot.queue = [];
        slot.current = null;
        slot.meta.nextRunAt = msg._nextRunAt ?? null;
        slot.meta.marketClosed = true;
        return;
      }
      if (msg.phase === "decision" && msg.decision?.action === "skipped_market_closed") {
        slot.meta.lastDecision = msg.decision;
        return; // 休市決策不進播放佇列（cycle_end 會處理待機顯示）
      }

      // 佇列防爆：超上限時丟掉中間過程、保留決策與輪結束（語義關鍵）
      if (slot.queue.length >= QUEUE_CAP) {
        slot.queue = slot.queue.filter(
          (e) => e.phase === "decision" || e.phase === "cycle_end"
        );
      }
      slot.queue.push(msg);
    }

    function connect() {
      ws = new WebSocket(WS_URL);
      ws.onopen = () => setConnected(true);
      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === "bot_activity" && msg.bot_id != null) handleEvent(msg);
        } catch {
          // 非 JSON 訊息直接忽略，別讓一則壞訊息毀掉連線
        }
      };
      ws.onclose = () => {
        setConnected(false);
        if (!closedByUs) reconnectTimer = setTimeout(connect, 2000);
      };
    }

    connect();

    // 播放器：每 TICK_MS 推進各 Bot 的佇列（控制最少顯示時間），
    // 公開狀態有變才 setState（避免每 200ms 無謂重繪）
    const tick = setInterval(() => {
      const now = Date.now();
      const slots = slotsRef.current;
      for (const slot of Object.values(slots)) {
        const minMs =
          slot.current?.phase === "decision" ? DECISION_MIN_MS : PHASE_MIN_MS;
        if (slot.current && now - slot.shownAt >= minMs) {
          if (slot.queue.length > 0) {
            applyEvent(slot, slot.queue.shift(), now);
          } else if (slot.current.phase === "cycle_end") {
            slot.current = null; // 一輪播完 → 進待機（倒數）
          }
          // 中間階段播完但下一則還沒到（真的還在跑）→ 維持現狀等真事件
        } else if (!slot.current && slot.queue.length > 0) {
          applyEvent(slot, slot.queue.shift(), now);
        }
      }
      const snapshot = {};
      for (const [id, slot] of Object.entries(slots)) {
        snapshot[id] = publicState(slot, now);
      }
      const serialized = JSON.stringify(snapshot);
      if (serialized !== lastSnapshotRef.current) {
        lastSnapshotRef.current = serialized;
        setActivityByBot(snapshot);
      }
    }, TICK_MS);

    return () => {
      closedByUs = true;
      clearTimeout(reconnectTimer);
      clearInterval(tick);
      if (ws) ws.close();
    };
  }, []);

  return { connected, activityByBot, feed };
}
