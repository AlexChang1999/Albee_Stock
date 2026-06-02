// ============================================================
// Bot 績效顯示的小工具
// ============================================================
// 把純粹「資料轉換」的邏輯從元件抽出來，好處有二：
//   1. 元件檔只負責畫面，職責單純
//   2. 純函式（同樣輸入永遠同樣輸出、不碰畫面）最好寫測試

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
  return [
    ["勝率", `${stats.win_rate_pct}%`],
    ["報酬率", `${ret}%`, retColor],
    ["交易次數", stats.num_trades],
    ["最大回撤", `${stats.max_drawdown_pct}%`],
  ];
}
