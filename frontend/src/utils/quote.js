// ============================================================
// 報價相關純函式工具
// ============================================================
// 抽成純函式（同樣輸入 → 同樣輸出、不碰畫面/網路），方便寫單元測試。

// 比較新價與前一筆價，判斷「漲 / 跌 / 平」。
// 回傳 "up" | "down" | "flat"，畫面再依此決定顏色（綠/紅/灰）。
export function quoteDirection(price, prevPrice) {
  if (prevPrice === null || prevPrice === undefined || price === prevPrice) {
    return "flat";
  }
  return price > prevPrice ? "up" : "down";
}

// 把價格格式化成固定兩位小數字串（null/未定義時回傳 "—"）。
export function formatPrice(price) {
  if (price === null || price === undefined || Number.isNaN(price)) {
    return "—";
  }
  return Number(price).toFixed(2);
}
