// ============================================================
// filterTrades：交易紀錄前端過濾（純函式）
// ============================================================
// Phase 9 step-02：交易紀錄頁的篩選一律在前端對「已抓回的 /trades 資料」過濾，
// 不改後端端點（資料量小，前端過濾就夠）。抽成純函式方便單元測試。
//
// 參數 filters（皆可選，空 = 不限制該維度）：
//   botId    — 數字或字串的 bot_id；"" / null = 全部
//   symbol   — 股票代號子字串（不分大小寫）；"" = 全部
//   side     — "buy" / "sell"；"" = 全部
//   dateFrom — 起始日 "YYYY-MM-DD"（含）；"" = 不限
//   dateTo   — 結束日 "YYYY-MM-DD"（含）；"" = 不限
//
// 回傳：符合所有條件的交易陣列（不改動原陣列）。

// 把交易時間取出 "YYYY-MM-DD"（用當地時間，與表格顯示一致）。
function toDateKey(value) {
  if (!value) return "";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "";
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export function filterTrades(trades, filters = {}) {
  const { botId = "", symbol = "", side = "", dateFrom = "", dateTo = "" } =
    filters;

  if (!Array.isArray(trades)) return [];

  const symbolNeedle = String(symbol).trim().toUpperCase();
  const botNeedle = botId === "" || botId === null ? null : Number(botId);

  return trades.filter((t) => {
    // 依 Bot
    if (botNeedle !== null && Number(t.bot_id) !== botNeedle) return false;
    // 依標的（子字串、不分大小寫）
    if (symbolNeedle && !String(t.symbol || "").toUpperCase().includes(symbolNeedle))
      return false;
    // 依買賣別
    if (side && t.side !== side) return false;
    // 依日期區間（含端點）
    if (dateFrom || dateTo) {
      const key = toDateKey(t.created_at);
      if (!key) return false;
      if (dateFrom && key < dateFrom) return false;
      if (dateTo && key > dateTo) return false;
    }
    return true;
  });
}
