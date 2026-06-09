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
];

// 策略代號 → 中文標籤的單一來源（找不到就回原代號，不會壞畫面）。
// 取代各元件各自寫一份對照，避免有的頁面顯示中文、有的印出 "ma_crossover"。
export function strategyLabel(key) {
  return STRATEGIES.find((s) => s.value === key)?.label || key;
}
