// ============================================================
// 全站共用常數
// ============================================================
// 把「多個元件都會用到的固定資料」集中放這裡，避免每個檔案各寫一份、
// 改動時要改好幾個地方。目前放策略清單。

// 可選的策略清單（對應後端的策略註冊表）
// 建立 Bot、編輯 Bot、回測三個地方都會用到這份清單。
export const STRATEGIES = [
  { value: "ma_crossover", label: "均線交叉" },
  { value: "rsi", label: "RSI" },
  { value: "macd", label: "MACD" },
  { value: "bollinger", label: "布林通道" },
  { value: "donchian", label: "唐奇安通道突破" },
  { value: "stochastic", label: "KD 隨機指標" },
  { value: "momentum", label: "動量" },
  { value: "williams_r", label: "威廉指標" },
  { value: "adx_trend", label: "ADX 趨勢" },
  { value: "composite", label: "策略組合" },
  { value: "script_breakout", label: "突破續抱（事件式）" },
  { value: "snr_3_0", label: "SNR 3.0 供需區" },
];

// 策略代號 → 中文標籤的單一來源（找不到就回原代號，不會壞畫面）。
// 取代各元件各自寫一份對照，避免有的頁面顯示中文、有的印出 "ma_crossover"。
export function strategyLabel(key) {
  return STRATEGIES.find((s) => s.value === key)?.label || key;
}

// K 線時間框架清單（M2/M3.5）——與後端 `backend/services/timeframes.py` 的
// ALL_TIMEFRAMES 同一份清單，後端加減框架時兩邊要一起改。
export const TIMEFRAMES = [
  "1Min", "5Min", "15Min", "30Min", "1Hour", "2Hour", "4Hour", "1Day",
];
export const DEFAULT_TIMEFRAME = "1Day";

// 回測區間快捷選項（天數）。選「最長」送 ~26 年（2000→2026），後端會自動改用
// yfinance 抓長歷史（Alpaca 免費版抓不到那麼久）。選了會填進「回測天數」欄。
export const BACKTEST_RANGES = [
  { value: 365, label: "近 1 年" },
  { value: 1825, label: "近 5 年" },
  { value: 3650, label: "近 10 年" },
  { value: 9500, label: "最長（2000 起）" },
];
