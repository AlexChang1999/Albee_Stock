// ============================================================
// 數字格式化純函式
// ============================================================

// 把大數字縮寫成好讀的單位：兆 T / 十億 B / 百萬 M / 千 K。
// 例：3,500,000,000,000 → "3.50T"；1,200,000,000 → "1.20B"。
// 財報、市值動輒幾千億，直接印一長串數字看不懂，縮寫比較直覺。
export function formatCompact(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  const n = Number(value);
  const abs = Math.abs(n);
  const sign = n < 0 ? "-" : "";
  if (abs >= 1e12) return `${sign}${(abs / 1e12).toFixed(2)}T`;
  if (abs >= 1e9) return `${sign}${(abs / 1e9).toFixed(2)}B`;
  if (abs >= 1e6) return `${sign}${(abs / 1e6).toFixed(2)}M`;
  if (abs >= 1e3) return `${sign}${(abs / 1e3).toFixed(2)}K`;
  return `${sign}${abs}`;
}

// 把小數比率轉成百分比字串（0.0052 → "0.52%"）。null → "—"。
export function formatPercent(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `${(Number(value) * 100).toFixed(2)}%`;
}
