// ============================================================
// BotAvatar — Bot 的方塊像素頭像
// ============================================================
// 根據傳入的 seed（通常是 Bot 的 id + 名字）產生一個獨一無二、
// 方塊像素風、左右對稱的可愛頭像。同一個 seed 永遠長一樣。
//
// 用法：<BotAvatar seed="1-我的Bot" size={40} />

// 把字串轉成一個穩定的數字（簡單的字串雜湊）
function hashString(str) {
  let h = 0;
  for (let i = 0; i < str.length; i++) {
    // h * 31 + 字元碼，是常見的字串雜湊算法
    h = (h << 5) - h + str.charCodeAt(i);
    h |= 0; // 保持在 32 位元整數範圍
  }
  return Math.abs(h);
}

// 可愛的暖色系配色盤（呼應 Claude 的橘，加上幾個柔和色）
const PALETTE = [
  "#D97757", // Claude 橘
  "#E8A87C", // 杏桃
  "#F2C14E", // 暖黃
  "#7FB069", // 抹茶綠
  "#6FB3C9", // 天空藍
  "#9B8BC4", // 薰衣草紫
  "#E07A9E", // 玫瑰粉
];

export default function BotAvatar({ seed = "bot", size = 40, active = false }) {
  const hash = hashString(seed);

  // 用雜湊值挑一個顏色
  const color = PALETTE[hash % PALETTE.length];

  const grid = 5; // 5x5 像素網格
  const cellSize = size / grid;
  const cells = [];

  // 只決定「左半邊 + 中間欄」，再鏡射到右半邊 → 左右對稱
  for (let y = 0; y < grid; y++) {
    for (let x = 0; x < Math.ceil(grid / 2); x++) {
      // 取雜湊值的某一個 bit 決定這格要不要填色
      const bitIndex = y * 3 + x;
      const filled = (hash >> bitIndex) & 1;
      if (filled) {
        cells.push([x, y]);
        const mirrorX = grid - 1 - x; // 對稱位置
        if (mirrorX !== x) cells.push([mirrorX, y]);
      }
    }
  }

  return (
    <svg
      width={size}
      height={size}
      viewBox={`0 0 ${size} ${size}`}
      style={{
        borderRadius: size * 0.25,
        background: "#f5ebe6",
        // 啟用中的 Bot 頭像會發光（用該 Bot 自己的顏色）
        boxShadow: active ? `0 0 0 2px #fff, 0 0 10px 3px ${color}` : "none",
        transition: "box-shadow 0.3s",
      }}
    >
      {cells.map(([x, y], i) => (
        <rect
          key={i}
          x={x * cellSize}
          y={y * cellSize}
          width={cellSize}
          height={cellSize}
          rx={cellSize * 0.3} // 圓角，讓方塊更可愛
          ry={cellSize * 0.3}
          fill={color}
        />
      ))}
    </svg>
  );
}
