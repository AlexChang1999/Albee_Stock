// ============================================================
// BotAvatar — NFT 風機器人頭像（多部件隨機組合）
// ============================================================
// 概念跟 NFT 大頭貼（像 CryptoPunks / Bored Ape）一樣：
// 準備多種「部件」（底色、頭型、眼睛、天線、嘴巴、配色），
// 再依 seed（Bot 的 id+名字）把不同部件「隨機但固定」地組合起來。
//
// 「隨機但固定」= 同一個 seed 每次都長一樣（用雜湊決定），
// 但不同 Bot 幾乎不會撞臉。部件種類相乘 → 上千種組合。
//
// 規格統一：所有頭像都是同一個 viewBox(100x100) 與 size，
// 只有「外型」不同，大小邊界完全一致。
//
// 用法：<BotAvatar seed="1-我的Bot" size={56} active={true} />

// 把字串轉成穩定的數字（簡單字串雜湊）
function hashString(str) {
  let h = 2166136261;
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i);
    h = Math.imul(h, 16777619); // FNV-1a，散布得比較均勻
  }
  return Math.abs(h);
}

// 霓虹色盤（部件用色從這裡挑）
const NEON = [
  "#00f0ff", "#ff00a0", "#00ff9f", "#ff6b00",
  "#bd00ff", "#ffd000", "#2bb6ff", "#ff3b6b",
];

// 頭像底色漸層（多款，像 NFT 的不同稀有背景）
const BG_GRADS = [
  ["#0a0e1a", "#16203a"], // 深藍黑
  ["#1a1030", "#301a4a"], // 深紫
  ["#04201c", "#0a3a30"], // 深綠
  ["#2a1208", "#3a2010"], // 深棕橘
  ["#0a1a2a", "#10304a"], // 海藍
  ["#1a0a1a", "#300a28"], // 暗紅紫
];

// ---------- 各部件的畫法（回傳 SVG 片段）----------
// 每個部件函式吃 (主色 color, 眼睛色 eye)，回傳對應的 SVG。
// 臉的主要範圍約在 x/y 22~78。

// 頭型：6 款外框
function head(variant, color) {
  const fill = color;
  const common = { fill, fillOpacity: 0.16, stroke: color, strokeWidth: 3 };
  switch (variant) {
    case 0: return <rect x="22" y="22" width="56" height="56" rx="14" {...common} />;
    case 1: return <rect x="20" y="24" width="60" height="52" rx="26" {...common} />; // 膠囊
    case 2: return <circle cx="50" cy="50" r="29" {...common} />; // 圓
    case 3: return <polygon points="50,20 80,38 80,68 50,82 20,68 20,38" {...common} />; // 六角
    case 4: return <rect x="24" y="24" width="52" height="52" rx="4" {...common} />; // 方
    default: return <polygon points="50,20 78,34 74,74 26,74 22,34" {...common} />; // 盾
  }
}

// 眼睛：6 款
function eyes(variant, eye, glow) {
  const f = { fill: eye, filter: glow };
  switch (variant) {
    case 0: // 方形雙眼
      return (<>
        <rect x="33" y="44" width="12" height="12" rx="3" {...f} />
        <rect x="55" y="44" width="12" height="12" rx="3" {...f} />
      </>);
    case 1: // 圓形雙眼
      return (<>
        <circle cx="39" cy="50" r="6" {...f} />
        <circle cx="61" cy="50" r="6" {...f} />
      </>);
    case 2: // 橫條 LED
      return (<>
        <rect x="32" y="48" width="14" height="5" rx="2.5" {...f} />
        <rect x="54" y="48" width="14" height="5" rx="2.5" {...f} />
      </>);
    case 3: // 獨眼（中央大圓）
      return <circle cx="50" cy="50" r="9" {...f} />;
    case 4: // 三眼
      return (<>
        <circle cx="37" cy="48" r="5" {...f} />
        <circle cx="63" cy="48" r="5" {...f} />
        <circle cx="50" cy="60" r="4" {...f} />
      </>);
    default: // 星星眼
      return (<>
        <polygon points="39,44 41,50 47,50 42,54 44,60 39,56 34,60 36,54 31,50 37,50" {...f} />
        <polygon points="61,44 63,50 69,50 64,54 66,60 61,56 56,60 58,54 53,50 59,50" {...f} />
      </>);
  }
}

// 天線：5 款（含「無」）
function antenna(variant, color, glow) {
  const s = { stroke: color, strokeWidth: 3, filter: glow };
  switch (variant) {
    case 0: return null; // 無天線
    case 1: // 單天線 + 球
      return (<>
        <line x1="50" y1="6" x2="50" y2="22" {...s} />
        <circle cx="50" cy="6" r="4" fill={color} filter={glow} />
      </>);
    case 2: // 雙天線
      return (<>
        <line x1="36" y1="10" x2="40" y2="24" {...s} />
        <line x1="64" y1="10" x2="60" y2="24" {...s} />
        <circle cx="36" cy="9" r="3.5" fill={color} filter={glow} />
        <circle cx="64" cy="9" r="3.5" fill={color} filter={glow} />
      </>);
    case 3: // 雷達碟
      return (<>
        <line x1="50" y1="8" x2="50" y2="22" {...s} />
        <ellipse cx="50" cy="8" rx="9" ry="3.5" fill={color} fillOpacity="0.5" stroke={color} strokeWidth="2" />
      </>);
    default: // 莫霍克鋸齒
      return <polygon points="38,22 42,8 46,22 50,8 54,22 58,8 62,22" fill={color} fillOpacity="0.6" stroke={color} strokeWidth="2" filter={glow} />;
  }
}

// 嘴巴：5 款
function mouth(variant, color) {
  const fill = { fill: color, fillOpacity: 0.6 };
  switch (variant) {
    case 0: // 柵欄
      return (<>
        <rect x="36" y="64" width="28" height="8" rx="2" {...fill} />
        <line x1="44" y1="64" x2="44" y2="72" stroke="#0a0e1a" strokeWidth="2" />
        <line x1="52" y1="64" x2="52" y2="72" stroke="#0a0e1a" strokeWidth="2" />
        <line x1="60" y1="64" x2="60" y2="72" stroke="#0a0e1a" strokeWidth="2" />
      </>);
    case 1: // 微笑弧
      return <path d="M38 64 Q50 74 62 64" fill="none" stroke={color} strokeWidth="3" strokeLinecap="round" />;
    case 2: // 一直線
      return <rect x="38" y="66" width="24" height="4" rx="2" {...fill} />;
    case 3: // 點陣
      return (<>
        {[40, 48, 56, 64].map((x) => (
          <rect key={x} x={x} y="65" width="5" height="5" rx="1.5" {...fill} />
        ))}
      </>);
    default: // 方框面板
      return <rect x="38" y="63" width="24" height="9" rx="2" fill="none" stroke={color} strokeWidth="2.5" />;
  }
}

export default function BotAvatar({ seed = "bot", size = 56, active = false }) {
  const hash = hashString(seed);
  // 用雜湊的不同「位元段」決定各部件，彼此獨立 → 組合多。
  const color = NEON[hash % NEON.length]; // 主色
  const eye = NEON[(hash >> 4) % NEON.length]; // 眼睛色（可能不同）
  const bg = BG_GRADS[(hash >> 8) % BG_GRADS.length]; // 底色漸層
  const headV = (hash >> 11) % 6;
  const eyeV = (hash >> 14) % 6;
  const antV = (hash >> 17) % 5;
  const mouthV = (hash >> 20) % 5;

  const glowId = `glow-${hash}`;
  const bgId = `bg-${hash}`;
  const glow = `url(#${glowId})`;

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 100 100"
      style={{
        borderRadius: size * 0.22,
        // 啟用中：白框 + 主色光暈；停用：細淡邊
        boxShadow: active
          ? `0 0 0 2px #fff, 0 0 14px 3px ${color}`
          : `inset 0 0 0 1px ${color}33`,
        transition: "box-shadow 0.3s",
      }}
    >
      <defs>
        {/* 霓虹發光濾鏡 */}
        <filter id={glowId} x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="2.2" result="b" />
          <feMerge>
            <feMergeNode in="b" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
        {/* 隨機底色漸層 */}
        <linearGradient id={bgId} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor={bg[0]} />
          <stop offset="1" stopColor={bg[1]} />
        </linearGradient>
      </defs>

      {/* 底 */}
      <rect x="0" y="0" width="100" height="100" fill={`url(#${bgId})`} />

      {/* 依 seed 組合各部件 */}
      {antenna(antV, color, glow)}
      {head(headV, color)}
      {eyes(eyeV, eye, glow)}
      {mouth(mouthV, color)}
    </svg>
  );
}
