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
];
