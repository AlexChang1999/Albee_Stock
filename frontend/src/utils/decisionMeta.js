// ============================================================
// decisionMeta：決策 action → 顯示標籤 + 配色（共用純函式）
// ============================================================
// DecisionsPage（審計表格）、BotActivityStatus（卡片即時動畫）、
// DecisionFeed（即時決策流）三處共用同一套映射，
// 顏色一律取自 theme 的 NEON 色票（深底主題勿寫死淺色 hex）。

import { NEON } from "../theme";

// action → 顯示標籤 + 配色（涵蓋有成交與沒成交的決策；與後端
// backend/models/decision_log.py 的 ACTION_* 常數一一對應）
export const ACTION_META = {
  bought: { label: "買進", color: NEON.green },
  sold: { label: "賣出", color: NEON.red },
  hold: { label: "觀望/續抱", color: "text.secondary" },
  skipped_market_closed: { label: "休市跳過", color: NEON.magenta },
  skipped_no_buying_power: { label: "購買力不足", color: NEON.magenta },
  skipped_circuit_breaker: { label: "熔斷跳過", color: NEON.magenta },
};

export function actionMeta(action) {
  return ACTION_META[action] || { label: action || "—", color: "text.secondary" };
}

// 賣出細分 exit_kind → 標籤 + 配色（與 backend/models/decision_log.py 的 EXIT_KIND_* 對應）。
// 只在「賣出」紀錄才有；其餘決策回 null（畫面不顯示 exit chip）。
export const EXIT_KIND_META = {
  stop_loss: { label: "止損", color: NEON.red },
  take_profit: { label: "停利", color: NEON.green },
  trailing: { label: "追蹤止損", color: NEON.red },
  signal_reversal: { label: "策略反轉", color: NEON.magenta },
  broker_settled: { label: "券商成交", color: "text.secondary" },
};

export function exitKindMeta(kind) {
  return EXIT_KIND_META[kind] || null;
}
