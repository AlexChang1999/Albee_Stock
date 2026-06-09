// ============================================================
// Bot 績效顯示的小工具
// ============================================================
// 把純粹「資料轉換」的邏輯從元件抽出來，好處有二：
//   1. 元件檔只負責畫面，職責單純
//   2. 純函式（同樣輸入永遠同樣輸出、不碰畫面）最好寫測試

import { signOf } from "./number";

// 把後端回傳的 Bot 績效 stats 轉成卡片要顯示的 [標籤, 值, 顏色] 陣列。
// 還沒有任何交易（num_trades = 0 或 stats 不存在）時，一律顯示 "-"，不放假數字。
export function statRows(stats) {
  if (!stats || stats.num_trades === 0) {
    return [
      ["勝率", "-"],
      ["報酬率", "-"],
      ["交易次數", stats ? stats.num_trades : "-"],
      ["最大回撤", "-"],
    ];
  }
  const ret = stats.return_pct;
  const retColor =
    ret > 0 ? "success.main" : ret < 0 ? "error.main" : "text.primary";
  // 報酬率補正負號（signOf）：漲跌不只靠綠/紅顏色表達，色盲/單色也讀得出方向。
  return [
    ["勝率", `${stats.win_rate_pct}%`],
    ["報酬率", `${signOf(ret)}${ret}%`, retColor],
    ["交易次數", stats.num_trades],
    ["最大回撤", `${stats.max_drawdown_pct}%`],
  ];
}

// 把後端的 last_checked_at（ISO 字串或 null）轉成「X 秒/分/小時前」這種好讀的相對時間。
// nowMs 預設取現在，傳入是為了好寫測試（同輸入同輸出）。
export function formatCheckedAgo(iso, nowMs = Date.now()) {
  if (!iso) return "尚未檢查";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "尚未檢查";
  const diffSec = Math.max(0, Math.round((nowMs - then) / 1000));
  if (diffSec < 60) return `${diffSec} 秒前檢查`;
  const diffMin = Math.round(diffSec / 60);
  if (diffMin < 60) return `${diffMin} 分鐘前檢查`;
  const diffHr = Math.round(diffMin / 60);
  if (diffHr < 24) return `${diffHr} 小時前檢查`;
  return `${Math.round(diffHr / 24)} 天前檢查`;
}

// 持倉狀態文字：有 peak_price = 持倉中（附峰值）、否則空手。
export function holdingText(peakPrice) {
  if (peakPrice == null) return "空手";
  return `持倉中 · 峰值 $${Number(peakPrice).toFixed(2)}`;
}
