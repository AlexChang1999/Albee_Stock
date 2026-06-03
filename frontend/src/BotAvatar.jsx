// ============================================================
// BotAvatar — 精緻淺色「徽章機器人」頭像（多部件隨機組合）
// ============================================================
// 概念：像一枚壓印在米白紙上的銀行印章 / 紀念幣——
//   圓形徽章底（暖白紙感 + 髮絲線外環），上面用「墨線 + 單一典雅點綴色」
//   勾勒一隻幾何小機器人。安靜、有質感，跟整站淺色金融風一致。
//
// 「隨機但固定」= 同一個 seed 每次都長一樣（用雜湊決定各部件），
// 但不同 Bot 幾乎不會撞臉。部件種類相乘 → 上千種組合。
//
// 規格統一：所有頭像都是同一個 viewBox(100x100) 與 size，
// 只有「外型 / 點綴色」不同，大小邊界完全一致。
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

// 墨色（線稿主色）：近墨藍黑，與全站文字色呼應
const INK = "#2b3142";

// 典雅點綴色盤（收斂、低彩度，不刺眼；每個 Bot 抽一個當識別色）
const ACCENTS = [
  "#1f6f54", // 森林綠
  "#b0883a", // 黃銅金
  "#3a6ea5", // 板岩藍
  "#a8553f", // 赤陶
  "#6d5a8c", // 暗紫
  "#2f8f86", // 青瓷綠
  "#9a7b2e", // 赭黃
  "#4a7a52", // 鼠尾草綠
];

// 徽章底色（暖白紙感漸層，多款細微差異）
const MEDALLIONS = [
  ["#ffffff", "#f2ece1"],
  ["#fdfbf7", "#ede7da"],
  ["#fbfaf6", "#ece5d7"],
  ["#fffdf9", "#efe8db"],
];

// ---------- 各部件畫法（回傳 SVG 片段）----------
// 線稿風：墨色描邊（stroke=INK），內部用點綴色淡淡填一層，眼睛/嘴用點綴色。
// 臉的主要範圍約在 x/y 26~74。

// 頭型：6 款外框（墨線描邊 + 點綴色淡填）
function head(variant, accent) {
  const c = {
    fill: accent,
    fillOpacity: 0.12,
    stroke: INK,
    strokeWidth: 2.4,
    strokeLinejoin: "round",
  };
  switch (variant) {
    case 0: return <rect x="28" y="30" width="44" height="44" rx="12" {...c} />;
    case 1: return <rect x="26" y="32" width="48" height="40" rx="20" {...c} />; // 膠囊
    case 2: return <circle cx="50" cy="52" r="23" {...c} />; // 圓
    case 3: return <polygon points="50,28 72,40 72,64 50,76 28,64 28,40" {...c} />; // 六角
    case 4: return <rect x="29" y="31" width="42" height="42" rx="4" {...c} />; // 方
    default: return <polygon points="50,28 71,38 68,72 32,72 29,38" {...c} />; // 盾
  }
}

// 眼睛：6 款（點綴色實心）
function eyes(variant, accent) {
  const f = { fill: accent };
  switch (variant) {
    case 0: // 方形雙眼
      return (<>
        <rect x="37" y="47" width="9" height="9" rx="2.5" {...f} />
        <rect x="54" y="47" width="9" height="9" rx="2.5" {...f} />
      </>);
    case 1: // 圓形雙眼
      return (<>
        <circle cx="41" cy="51" r="4.5" {...f} />
        <circle cx="59" cy="51" r="4.5" {...f} />
      </>);
    case 2: // 橫條 LED
      return (<>
        <rect x="36" y="49" width="11" height="4" rx="2" {...f} />
        <rect x="53" y="49" width="11" height="4" rx="2" {...f} />
      </>);
    case 3: // 獨眼（中央圓 + 墨色外環）
      return (<>
        <circle cx="50" cy="51" r="7.5" fill="none" stroke={INK} strokeWidth="2.2" />
        <circle cx="50" cy="51" r="3.5" {...f} />
      </>);
    case 4: // 三眼
      return (<>
        <circle cx="40" cy="49" r="3.6" {...f} />
        <circle cx="60" cy="49" r="3.6" {...f} />
        <circle cx="50" cy="58" r="3" {...f} />
      </>);
    default: // 護目鏡橫條（墨框 + 點綴填）
      return (<>
        <rect x="35" y="46" width="30" height="9" rx="4.5" fill="none" stroke={INK} strokeWidth="2.2" />
        <circle cx="42" cy="50.5" r="2.4" {...f} />
        <circle cx="58" cy="50.5" r="2.4" {...f} />
      </>);
  }
}

// 天線：5 款（含「無」）。墨線桿 + 點綴色頂端。
function antenna(variant, accent) {
  const s = { stroke: INK, strokeWidth: 2.2, strokeLinecap: "round" };
  switch (variant) {
    case 0: return null; // 無天線
    case 1: // 單天線 + 球
      return (<>
        <line x1="50" y1="16" x2="50" y2="30" {...s} />
        <circle cx="50" cy="14" r="3.4" fill={accent} />
      </>);
    case 2: // 雙天線
      return (<>
        <line x1="40" y1="18" x2="42" y2="31" {...s} />
        <line x1="60" y1="18" x2="58" y2="31" {...s} />
        <circle cx="40" cy="16" r="2.8" fill={accent} />
        <circle cx="60" cy="16" r="2.8" fill={accent} />
      </>);
    case 3: // 雷達碟
      return (<>
        <line x1="50" y1="18" x2="50" y2="30" {...s} />
        <ellipse cx="50" cy="16" rx="8" ry="3" fill={accent} fillOpacity="0.5" stroke={INK} strokeWidth="1.8" />
      </>);
    default: // 一字橫桿 + 雙端點
      return (<>
        <line x1="38" y1="22" x2="62" y2="22" {...s} />
        <circle cx="38" cy="22" r="2.6" fill={accent} />
        <circle cx="62" cy="22" r="2.6" fill={accent} />
        <line x1="50" y1="22" x2="50" y2="31" {...s} />
      </>);
  }
}

// 嘴巴：5 款（墨線為主，少量點綴色）
function mouth(variant, accent) {
  switch (variant) {
    case 0: // 柵欄
      return (<>
        <rect x="40" y="63" width="20" height="6" rx="2" fill="none" stroke={INK} strokeWidth="2" />
        <line x1="47" y1="63" x2="47" y2="69" stroke={INK} strokeWidth="1.6" />
        <line x1="53" y1="63" x2="53" y2="69" stroke={INK} strokeWidth="1.6" />
      </>);
    case 1: // 微笑弧
      return <path d="M41 64 Q50 71 59 64" fill="none" stroke={INK} strokeWidth="2.4" strokeLinecap="round" />;
    case 2: // 一直線
      return <line x1="42" y1="66" x2="58" y2="66" stroke={INK} strokeWidth="2.4" strokeLinecap="round" />;
    case 3: // 點陣
      return (<>
        {[43, 50, 57].map((x) => (
          <circle key={x} cx={x} cy="66" r="2" fill={accent} />
        ))}
      </>);
    default: // 方框面板
      return <rect x="42" y="63" width="16" height="6" rx="1.5" fill="none" stroke={INK} strokeWidth="2" />;
  }
}

export default function BotAvatar({ seed = "bot", size = 56, active = false }) {
  const hash = hashString(seed);
  // 用雜湊的不同「位元段」決定各部件，彼此獨立 → 組合多。
  const accent = ACCENTS[hash % ACCENTS.length]; // 識別點綴色
  const med = MEDALLIONS[(hash >> 8) % MEDALLIONS.length]; // 徽章底色
  const headV = (hash >> 11) % 6;
  const eyeV = (hash >> 14) % 6;
  const antV = (hash >> 17) % 5;
  const mouthV = (hash >> 20) % 5;

  const medId = `med-${hash}`;

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 100 100"
      style={{
        borderRadius: "50%",
        // 啟用中：點綴色細環 + 柔和外暈；停用：極淡髮絲外環
        boxShadow: active
          ? `0 0 0 2px #fff, 0 0 0 3.5px ${accent}, 0 4px 12px -2px ${accent}55`
          : "0 1px 3px rgba(28,34,48,0.12)",
        transition: "box-shadow 0.25s",
      }}
    >
      <defs>
        {/* 暖白紙感徽章漸層 */}
        <radialGradient id={medId} cx="38%" cy="32%" r="80%">
          <stop offset="0" stopColor={med[0]} />
          <stop offset="1" stopColor={med[1]} />
        </radialGradient>
      </defs>

      {/* 徽章底 + 髮絲線外環 + 內細環（壓印幣感） */}
      <circle cx="50" cy="50" r="49" fill={`url(#${medId})`} />
      <circle cx="50" cy="50" r="48" fill="none" stroke="rgba(28,34,48,0.16)" strokeWidth="1.2" />
      <circle cx="50" cy="50" r="43" fill="none" stroke="rgba(28,34,48,0.08)" strokeWidth="1" />

      {/* 依 seed 組合各部件（墨線 + 點綴色） */}
      {antenna(antV, accent)}
      {head(headV, accent)}
      {eyes(eyeV, accent)}
      {mouth(mouthV, accent)}
    </svg>
  );
}
