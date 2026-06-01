// ============================================================
// BotAvatar — Cyberpunk 機器人頭像
// ============================================================
// 深色底 + 霓虹色機器人臉。主色與眼睛色由 seed（Bot id+名字）決定，
// 所以每個 Bot 顏色不同，但都長得像機器人。
//
// 用法：<BotAvatar seed="1-我的Bot" size={40} active={true} />

// 把字串轉成穩定的數字（簡單字串雜湊）
function hashString(str) {
  let h = 0;
  for (let i = 0; i < str.length; i++) {
    h = (h << 5) - h + str.charCodeAt(i);
    h |= 0;
  }
  return Math.abs(h);
}

// Cyberpunk 霓虹色盤
const NEON = [
  "#00f0ff", // 青
  "#ff00a0", // 洋紅
  "#a3ff00", // 螢光綠
  "#ff6b00", // 霓虹橘
  "#bd00ff", // 紫
  "#00ff9f", // 薄荷綠
];

export default function BotAvatar({ seed = "bot", size = 40, active = false }) {
  const hash = hashString(seed);
  const color = NEON[hash % NEON.length]; // 機器人主色
  const eyeColor = NEON[(hash >> 3) % NEON.length]; // 眼睛色（可能不同）
  const glowId = `glow-${hash}`; // 發光濾鏡的唯一 id

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 100 100"
      style={{
        borderRadius: size * 0.22,
        background: "#0a0e1a", // 深色底（填滿）
        boxShadow: active
          ? `0 0 0 2px #fff, 0 0 12px 3px ${color}`
          : `inset 0 0 0 1px ${color}33`,
        transition: "box-shadow 0.3s",
      }}
    >
      <defs>
        {/* 霓虹發光效果 */}
        <filter id={glowId} x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="2.5" result="b" />
          <feMerge>
            <feMergeNode in="b" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      {/* 天線 */}
      <line
        x1="50"
        y1="6"
        x2="50"
        y2="22"
        stroke={color}
        strokeWidth="3"
        filter={`url(#${glowId})`}
      />
      <circle cx="50" cy="6" r="4" fill={color} filter={`url(#${glowId})`} />

      {/* 機器人頭（填色 + 霓虹描邊） */}
      <rect
        x="22"
        y="22"
        width="56"
        height="56"
        rx="12"
        fill={color}
        fillOpacity="0.18"
        stroke={color}
        strokeWidth="3"
      />

      {/* 兩顆發光眼睛 */}
      <rect
        x="33"
        y="42"
        width="12"
        height="12"
        rx="3"
        fill={eyeColor}
        filter={`url(#${glowId})`}
      />
      <rect
        x="55"
        y="42"
        width="12"
        height="12"
        rx="3"
        fill={eyeColor}
        filter={`url(#${glowId})`}
      />

      {/* 嘴巴（柵欄狀） */}
      <rect x="36" y="64" width="28" height="8" rx="2" fill={color} fillOpacity="0.6" />
      <line x1="44" y1="64" x2="44" y2="72" stroke="#0a0e1a" strokeWidth="2" />
      <line x1="52" y1="64" x2="52" y2="72" stroke="#0a0e1a" strokeWidth="2" />
      <line x1="60" y1="64" x2="60" y2="72" stroke="#0a0e1a" strokeWidth="2" />
    </svg>
  );
}
