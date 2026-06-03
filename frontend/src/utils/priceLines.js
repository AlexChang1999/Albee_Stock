// ============================================================
// priceLines：依 Bot 風控資料算出圖表上的「水位線」
// ============================================================
// 一個服役中的 Bot 會在圖上畫最多三條水平線，讓你一眼看到保護設在哪：
//   1. 進場均價線（白/灰虛線）：avg_entry_price
//   2. 止損線（紅實線）：進場價 ×(1 − stop_loss_pct)
//   3. 追蹤止盈線（綠實線）：持倉最高價 ×(1 − trailing_stop_pct)，隨價創高自動上移
//
// 抽成純函式（輸入 bot 物件 → 輸出線陣列）是為了好寫測試：
//   不用真的畫圖，只驗算出來的價格對不對。
//
// 回傳格式給 LightweightChart 的 priceLines prop 直接用：
//   { price, color, title, dashed }

const COLOR_ENTRY = "#9e9e9e"; // 灰：進場均價
const COLOR_STOP = "#b23b32"; // 紅：止損
const COLOR_TRAIL = "#1f7a5a"; // 綠：追蹤止盈

export function buildBotPriceLines(bot) {
  if (!bot) return [];

  const lines = [];
  const entry = bot.avg_entry_price;

  // 1. 進場均價線（要有持倉、拿得到均價才畫）
  if (entry != null) {
    lines.push({
      price: entry,
      color: COLOR_ENTRY,
      title: "進場均價",
      dashed: true,
    });

    // 2. 止損線：需要進場價 + 止損百分比
    if (bot.stop_loss_pct != null) {
      lines.push({
        price: entry * (1 - bot.stop_loss_pct),
        color: COLOR_STOP,
        title: "止損",
        dashed: false,
      });
    }
  }

  // 3. 追蹤止盈線：用持倉最高價回落一定比例（與進場價無關，所以獨立判斷）
  if (bot.peak_price != null && bot.trailing_stop_pct != null) {
    lines.push({
      price: bot.peak_price * (1 - bot.trailing_stop_pct),
      color: COLOR_TRAIL,
      title: "追蹤止盈",
      dashed: false,
    });
  }

  return lines;
}

// 從一籃 Bot 裡挑出「正在跑某檔股票」的那一個（給圖表配對用）。
// 同一檔可能有多個 Bot，優先取啟用中的；都沒有就取第一個符合的。
export function findBotForSymbol(bots, symbol) {
  if (!bots || !symbol) return null;
  const matches = bots.filter((b) => b.symbol === symbol);
  if (matches.length === 0) return null;
  return matches.find((b) => b.is_active) || matches[0];
}
