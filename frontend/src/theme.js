// ============================================================
// 全站主題設定（深藍交易終端機：deep-blue dark + 玻璃擬態 glassmorphism）
// ============================================================
// 重點觀念：MUI 的 components.styleOverrides 可以「一次改掉全站」
// 某種元件的長相。例如下面改了 MuiCard，整頁所有 <Card> 自動變成
// 深色玻璃霧面卡片，不必逐個加 sx。這是全套換皮最省力又最一致的做法。
//
// 為什麼用深藍色（藍圖 Phase 3）？
//   金融盯盤需長時間專注，深藍底比亮白底不刺眼、更有科技沉浸感；
//   同時讓獲利（青綠）、虧損（洋紅）與圖表水位線等關鍵數據更跳脫、好辨識。
//
// 為什麼獨立成一個檔案？
//   主題設定（顏色、字體、元件樣式）跟「畫面邏輯」是兩回事。
//   抽出來後 App.jsx 只專心管資料流，要調色改字體都來這裡找。

import { createTheme } from "@mui/material/styles";

// 霓虹色票（深底版：當「彩色 accent」用，與 index.css、BotAvatar、Header 呼應）
// 比亮色版更亮一階，才能在深藍底上發光跳出來。
export const NEON = {
  cyan: "#22d3ee", // 主色
  magenta: "#ff3d8b", // 輔色 / 虧損
  green: "#00e5a0", // 漲 / 成功 / 獲利
  red: "#ff4d6d", // 跌 / 危險
};

// 玻璃霧面的共用底樣式（深色版）：半透明深藍底 + 背景模糊 + 細彩色邊框。
// backdropFilter 讓卡片後面的彩色光暈透出來、變柔，就是「毛玻璃」效果。
const glass = {
  background:
    "linear-gradient(160deg, rgba(24,34,66,0.78), rgba(16,24,48,0.62))",
  backdropFilter: "blur(16px)",
  WebkitBackdropFilter: "blur(16px)",
  border: "1px solid rgba(34,211,238,0.16)",
  borderRadius: 18,
  boxShadow: "0 8px 28px rgba(0,0,0,0.35)", // 深色陰影，卡片浮起來
};

export const theme = createTheme({
  palette: {
    mode: "dark", // 深色模式
    primary: { main: NEON.cyan },
    secondary: { main: NEON.magenta },
    success: { main: NEON.green },
    error: { main: NEON.red },
    warning: { main: "#f5a623" },
    // 背景設透明，讓 index.css 的深藍光暈背景能透出來
    background: { default: "transparent", paper: "rgba(20,30,58,0.72)" },
    text: { primary: "#e8ecf8", secondary: "rgba(232,236,248,0.6)" },
    divider: "rgba(255,255,255,0.1)",
  },
  typography: {
    fontFamily: '"Outfit", "Microsoft JhengHei", sans-serif',
    // 標題系列改用 Sora（幾何未來感顯示字體）
    h6: { fontFamily: '"Sora", sans-serif', fontWeight: 700, letterSpacing: 0.3 },
    h5: { fontFamily: '"Sora", sans-serif', fontWeight: 700 },
    subtitle2: { fontWeight: 600 },
    button: { textTransform: "none", fontWeight: 600 }, // 按鈕不要全大寫
  },
  shape: { borderRadius: 14 },
  components: {
    // 卡片：深藍玻璃 + 滑入時青色邊框、陰影加深
    MuiCard: {
      styleOverrides: {
        root: {
          ...glass,
          backgroundImage: "none",
          transition: "border-color .3s, box-shadow .3s",
          "&:hover": {
            borderColor: "rgba(34,211,238,0.42)",
            boxShadow: "0 12px 36px rgba(34,211,238,0.16)",
          },
        },
      },
    },
    // Paper（outlined 變體用在 Bot 卡片、表格容器）：同深藍玻璃風
    MuiPaper: {
      styleOverrides: {
        outlined: {
          ...glass,
          backgroundImage: "none",
          transition: "border-color .3s, box-shadow .3s",
          "&:hover": {
            borderColor: "rgba(34,211,238,0.4)",
            boxShadow: "0 12px 32px rgba(34,211,238,0.14)",
          },
        },
      },
    },
    // 實心按鈕：青色漸層 + 柔和彩色陰影
    MuiButton: {
      styleOverrides: {
        containedPrimary: {
          background: `linear-gradient(135deg, ${NEON.cyan}, #2bb6ff)`,
          color: "#04121f",
          fontWeight: 700,
          boxShadow: "0 4px 16px rgba(34,211,238,0.4)",
          "&:hover": {
            background: `linear-gradient(135deg, #18c4e0, #1aa6ff)`,
            boxShadow: "0 6px 22px rgba(34,211,238,0.55)",
          },
        },
      },
    },
    // 輸入框：深藍半透明底，聚焦時青色邊框
    MuiOutlinedInput: {
      styleOverrides: {
        root: {
          background: "rgba(12,20,40,0.5)",
          "& .MuiOutlinedInput-notchedOutline": {
            borderColor: "rgba(255,255,255,0.15)",
          },
          "&:hover .MuiOutlinedInput-notchedOutline": {
            borderColor: "rgba(34,211,238,0.5)",
          },
          "&.Mui-focused .MuiOutlinedInput-notchedOutline": {
            borderColor: NEON.cyan,
            boxShadow: "0 0 0 3px rgba(34,211,238,0.16)",
          },
        },
      },
    },
    // 表格儲存格：淡分隔線 + 大寫標題列
    MuiTableCell: {
      styleOverrides: {
        root: { borderColor: "rgba(255,255,255,0.08)" },
        head: {
          color: "rgba(232,236,248,0.55)",
          fontFamily: '"Sora", sans-serif',
          fontWeight: 600,
          letterSpacing: 0.5,
          textTransform: "uppercase",
          fontSize: 12,
        },
      },
    },
    // 分頁指示線：青色
    MuiTabs: {
      styleOverrides: {
        indicator: {
          height: 3,
          borderRadius: 3,
          background: NEON.cyan,
        },
      },
    },
    MuiTab: {
      styleOverrides: {
        root: {
          fontFamily: '"Sora", sans-serif',
          fontWeight: 600,
          fontSize: 15,
          color: "rgba(232,236,248,0.5)",
          "&.Mui-selected": { color: NEON.cyan },
        },
      },
    },
    // 提示訊息：深色
    MuiAlert: {
      styleOverrides: {
        root: { borderRadius: 12 },
      },
    },
    // 彈出視窗：深藍玻璃
    MuiDialog: {
      styleOverrides: { paper: { ...glass, backgroundImage: "none" } },
    },
  },
});
