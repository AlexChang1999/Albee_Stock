// ============================================================
// 全站主題設定（深藍沉浸金融風：深海軍藍底 + 發光數據色 + 襯線大標）
// ============================================================
// 重點觀念：MUI 的 components.styleOverrides 可以「一次改掉全站」
// 某種元件的長相。例如下面改了 MuiCard，整頁所有 <Card> 自動變成
// 深藍面板，不必逐個加 sx。這是全套換皮最省力又最一致的做法。
//
// 設計方向「深藍沉浸金融」（改版 Phase 3）：像專業交易終端機——
//   深海軍藍面板 + 冷光邊框 + 高對比數據色（獲利青綠 / 虧損洋紅）。
//   深色基底讓圖表水位線、AI 決策卡片成為視覺焦點，也減輕長時間盯盤疲勞。

import { createTheme } from "@mui/material/styles";

// 色票（深藍沉浸金融）。
// 注意：沿用既有 NEON 這個匯出名稱與鍵名（cyan/magenta/green/red），
// 讓 Header、StrategyWorkbench 等既有 import 不用改就能換上新色：
//   cyan    -> 主色（亮藍：行動、focus）   magenta -> 點綴（黃金：強調、收藏、EV 冠軍）
//   green   -> 上漲/獲利（青綠）           red     -> 下跌/虧損（洋紅）
export const NEON = {
  cyan: "#4da3ff", // 主色：亮藍（行動、focus、分頁指示）
  magenta: "#f5c451", // 點綴：黃金（強調、收藏、EV 冠軍）
  green: "#1fd6a0", // 獲利青綠
  red: "#ff5d7a", // 虧損洋紅
};

// 兩套底色變數（E1 亮色模式）：深藍沉浸（預設）與亮色。
// NEON 數據色兩個模式共用——深底上是冷光、亮底上是飽和點綴，對比都夠。
const MODES = {
  dark: {
    ink: "#e7edf7", // 主文字：近白冷光
    inkSoft: "#9aa9c2", // 次要文字：灰藍
    panel: "#0f1f3a", // 面板底：深海軍藍
    line: "rgba(255,255,255,0.09)", // 冷色髮絲線
    cardShadow:
      "0 1px 0 rgba(255,255,255,0.04) inset, 0 16px 32px -22px rgba(0,0,0,0.7)",
    cardShadowHover:
      "0 1px 0 rgba(255,255,255,0.05) inset, 0 22px 40px -24px rgba(0,0,0,0.8)",
  },
  light: {
    ink: "#16243f", // 主文字：深海軍藍（在淺底上）
    inkSoft: "#5a6a88", // 次要文字：灰藍
    panel: "#ffffff", // 面板底：白
    line: "rgba(22,36,63,0.14)", // 深色髮絲線
    cardShadow: "0 10px 24px -18px rgba(22,36,63,0.35)",
    cardShadowHover: "0 16px 32px -20px rgba(22,36,63,0.45)",
  },
};

// 依模式產整套 MUI 主題。元件 import { theme } 拿到的是深色預設，
// App.jsx 用 buildTheme(mode) 依使用者切換重建。
export function buildTheme(mode = "dark") {
  const C = MODES[mode] ?? MODES.dark;
  const INK = C.ink;
  const INK_SOFT = C.inkSoft;
  const PANEL = C.panel;
  const LINE = C.line;

  // 卡片共用底樣式：面板 + 細邊 + 陰影（兩模式同形、不同色）。
  const paperCard = {
    backgroundColor: PANEL,
    backgroundImage: "none",
    border: `1px solid ${LINE}`,
    borderRadius: 16,
    boxShadow: C.cardShadow,
    transition: "border-color .25s, box-shadow .25s, transform .25s",
  };

  return createTheme({
  palette: {
    mode,
    primary: { main: NEON.cyan },
    secondary: { main: NEON.magenta },
    success: { main: NEON.green },
    error: { main: NEON.red },
    warning: { main: NEON.magenta },
    // 背景透明，讓 index.css 的底色與光暈透出來（亮/暗由 body[data-mode] 切）
    background: { default: "transparent", paper: PANEL },
    text: { primary: INK, secondary: INK_SOFT },
    divider: LINE,
  },
  typography: {
    fontFamily: '"Manrope", "Microsoft JhengHei", sans-serif',
    // 標題系列改用 Fraunces（高對比襯線，高雅有個性）
    h4: { fontFamily: '"Fraunces", serif', fontWeight: 600, letterSpacing: "-0.01em" },
    h5: { fontFamily: '"Fraunces", serif', fontWeight: 600, letterSpacing: "-0.01em" },
    h6: { fontFamily: '"Fraunces", serif', fontWeight: 600, letterSpacing: "-0.005em" },
    subtitle2: { fontWeight: 600 },
    button: { textTransform: "none", fontWeight: 600 }, // 按鈕不要全大寫
  },
  shape: { borderRadius: 14 },
  components: {
    // 卡片：深藍面板，滑入時邊框轉亮藍、陰影加深並輕輕浮起
    MuiCard: {
      styleOverrides: {
        root: {
          ...paperCard,
          "&:hover": {
            borderColor: "rgba(77,163,255,0.45)",
            boxShadow: C.cardShadowHover,
          },
        },
      },
    },
    // Paper（outlined 變體用在 Bot 卡片、表格容器）：同深藍面板
    MuiPaper: {
      styleOverrides: {
        outlined: {
          ...paperCard,
          "&:hover": {
            borderColor: "rgba(77,163,255,0.35)",
          },
        },
      },
    },
    // 實心按鈕：亮藍實心，hover 加亮 + 冷光暈
    MuiButton: {
      styleOverrides: {
        root: { borderRadius: 10 },
        containedPrimary: {
          background: NEON.cyan,
          color: "#08152b",
          fontWeight: 700,
          boxShadow: "0 2px 10px rgba(77,163,255,0.3)",
          "&:hover": {
            background: "#6cb6ff",
            boxShadow: "0 4px 16px rgba(77,163,255,0.42)",
          },
        },
        outlinedPrimary: {
          borderColor: "rgba(77,163,255,0.5)",
          color: NEON.cyan,
          "&:hover": {
            borderColor: NEON.cyan,
            background: "rgba(77,163,255,0.1)",
          },
        },
      },
    },
    // 輸入框：深底，聚焦時亮藍細框 + 冷光圈
    MuiOutlinedInput: {
      styleOverrides: {
        root: {
          background: "rgba(255,255,255,0.03)",
          borderRadius: 10,
          "& .MuiOutlinedInput-notchedOutline": {
            borderColor: LINE,
          },
          "&:hover .MuiOutlinedInput-notchedOutline": {
            borderColor: "rgba(77,163,255,0.55)",
          },
          "&.Mui-focused .MuiOutlinedInput-notchedOutline": {
            borderColor: NEON.cyan,
            boxShadow: "0 0 0 3px rgba(77,163,255,0.16)",
          },
        },
      },
    },
    // 表格儲存格：髮絲分隔線 + 大寫標題列（小字、寬字距）
    MuiTableCell: {
      styleOverrides: {
        root: { borderColor: LINE },
        head: {
          color: INK_SOFT,
          fontFamily: '"Manrope", sans-serif',
          fontWeight: 700,
          letterSpacing: "0.06em",
          textTransform: "uppercase",
          fontSize: 11,
        },
      },
    },
    // 分頁指示線：亮藍細線
    MuiTabs: {
      styleOverrides: {
        indicator: {
          height: 2,
          borderRadius: 2,
          background: NEON.cyan,
        },
      },
    },
    MuiTab: {
      styleOverrides: {
        root: {
          fontFamily: '"Manrope", sans-serif',
          fontWeight: 600,
          fontSize: 15,
          letterSpacing: "0.01em",
          color: INK_SOFT,
          "&.Mui-selected": { color: INK },
        },
      },
    },
    // 提示訊息：圓角、柔和
    MuiAlert: {
      styleOverrides: {
        root: { borderRadius: 12, border: `1px solid ${LINE}` },
      },
    },
    // 彈出視窗：深藍面板
    MuiDialog: {
      styleOverrides: { paper: { ...paperCard } },
    },
    // 晶片：細邊、不要太搶眼
    MuiChip: {
      styleOverrides: {
        root: { fontWeight: 600, letterSpacing: "0.01em" },
      },
    },
  },
  });
}

// 深色預設：既有 import { theme } 不用改就照常運作
export const theme = buildTheme("dark");
