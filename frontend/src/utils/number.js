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

// 取數值的正負號字首：正數回 "+"，負數/零回 ""（負號由數字本身帶、零不標號）。
// 用途（無障礙 color-not-only）：漲跌不能只靠綠/紅顏色表達，
// 在數字前補 "+/-" 讓色盲或單色畫面也讀得出方向。
// 例：signOf(5.2) → "+"、signOf(-3) → ""（因 -3 已含負號）、signOf(0) → ""。
export function signOf(value) {
  const n = Number(value);
  if (!Number.isFinite(n) || n === 0) return "";
  return n > 0 ? "+" : "";
}

// 一般金額字串（千分位、無正負號）："$1,234" / "—"。
// 取代各元件 inline 的 `$${Number(v).toLocaleString()}`，集中一處好維護。
export function money(value) {
  if (value === null || value === undefined || value === "" || Number.isNaN(Number(value)))
    return "—";
  return `$${Number(value).toLocaleString()}`;
}

// 帶正負號的金額字串，符號永遠在錢號之前："+$12" / "-$5" / "$0" / "—"。
// 直接 `$${n}` 會印出 "$-5"（負號夾在中間、不好讀），故這裡把符號提前。
export function signedMoney(value) {
  if (value === null || value === undefined || value === "" || Number.isNaN(Number(value)))
    return "—";
  const n = Number(value);
  const sign = n > 0 ? "+" : n < 0 ? "-" : "";
  return `${sign}$${Math.abs(n)}`;
}
