// ============================================================
// 全站主題設定（霓虹儀表板：dark accent + 玻璃擬態 glassmorphism）
// ============================================================
// 重點觀念：MUI 的 components.styleOverrides 可以「一次改掉全站」
// 某種元件的長相。例如下面改了 MuiCard，整頁所有 <Card> 自動變成
// 玻璃霧面卡片，不必逐個加 sx。這是全套換皮最省力又最一致的做法。
//
// 為什麼獨立成一個檔案？
//   主題設定（顏色、字體、元件樣式）跟「畫面邏輯」是兩回事。
//   抽出來後 App.jsx 只專心管資料流，要調色改字體都來這裡找。

import { createTheme } from "@mui/material/styles";

// 霓虹色票（亮色版：當「彩色 accent」用，與 index.css、BotAvatar 呼應）
// Header 的漸層文字 / 發光 logo 也會 import 這個 NEON 來用。
export const NEON = {
  cyan: "#00b8d4", // 主色
  magenta: "#e6007a", // 輔色
  green: "#00b87a", // 漲 / 成功
  red: "#e63950", // 跌 / 危險
};

// 玻璃霧面的共用底樣式（亮色版）：半透明白底 + 背景模糊 + 細彩色邊框。
// backdropFilter 讓卡片後面的彩色光暈透出來、變柔，就是「毛玻璃」效果。
const glass = {
  background:
    "linear-gradient(160deg, rgba(255,255,255,0.85), rgba(255,255,255,0.7))",
  backdropFilter: "blur(16px)",
  WebkitBackdropFilter: "blur(16px)",
  border: "1px solid rgba(0,184,212,0.18)",
  borderRadius: 18,
  boxShadow: "0 6px 24px rgba(26,34,56,0.06)", // 柔和淺陰影，卡片浮起來
};

export const theme = createTheme({
  palette: {
    mode: "light", // 亮色模式
    primary: { main: NEON.cyan },
    secondary: { main: NEON.magenta },
    success: { main: NEON.green },
    error: { main: NEON.red },
    warning: { main: "#e08700" },
    // 背景設透明，讓 index.css 的彩色光暈背景能透出來
    background: { default: "transparent", paper: "rgba(255,255,255,0.8)" },
    text: { primary: "#1a2238", secondary: "rgba(26,34,56,0.58)" },
    divider: "rgba(26,34,56,0.1)",
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
    // 卡片：白玻璃 + 滑入時彩色邊框、陰影加深
    MuiCard: {
      styleOverrides: {
        root: {
          ...glass,
          backgroundImage: "none",
          transition: "border-color .3s, box-shadow .3s",
          "&:hover": {
            borderColor: "rgba(0,184,212,0.4)",
            boxShadow: "0 10px 32px rgba(0,184,212,0.12)",
          },
        },
      },
    },
    // Paper（outlined 變體用在 Bot 卡片、表格容器）：同白玻璃風
    MuiPaper: {
      styleOverrides: {
        outlined: {
          ...glass,
          backgroundImage: "none",
          transition: "border-color .3s, box-shadow .3s",
          "&:hover": {
            borderColor: "rgba(0,184,212,0.38)",
            boxShadow: "0 10px 28px rgba(0,184,212,0.1)",
          },
        },
      },
    },
    // 實心按鈕：青色漸層 + 柔和彩色陰影
    MuiButton: {
      styleOverrides: {
        containedPrimary: {
          background: `linear-gradient(135deg, ${NEON.cyan}, #2bb6ff)`,
          color: "#ffffff",
          fontWeight: 700,
          boxShadow: "0 4px 14px rgba(0,184,212,0.35)",
          "&:hover": {
            background: `linear-gradient(135deg, #00a5bf, #1aa6ff)`,
            boxShadow: "0 6px 20px rgba(0,184,212,0.45)",
          },
        },
      },
    },
    // 輸入框：白底，聚焦時青色邊框
    MuiOutlinedInput: {
      styleOverrides: {
        root: {
          background: "rgba(255,255,255,0.7)",
          "& .MuiOutlinedInput-notchedOutline": {
            borderColor: "rgba(26,34,56,0.15)",
          },
          "&:hover .MuiOutlinedInput-notchedOutline": {
            borderColor: "rgba(0,184,212,0.5)",
          },
          "&.Mui-focused .MuiOutlinedInput-notchedOutline": {
            borderColor: NEON.cyan,
            boxShadow: "0 0 0 3px rgba(0,184,212,0.12)",
          },
        },
      },
    },
    // 表格儲存格：淡分隔線 + 大寫標題列
    MuiTableCell: {
      styleOverrides: {
        root: { borderColor: "rgba(26,34,56,0.08)" },
        head: {
          color: "rgba(26,34,56,0.5)",
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
          color: "rgba(26,34,56,0.5)",
          "&.Mui-selected": { color: NEON.cyan },
        },
      },
    },
    // 提示訊息：亮色
    MuiAlert: {
      styleOverrides: {
        root: { borderRadius: 12 },
      },
    },
    // 彈出視窗：白玻璃
    MuiDialog: {
      styleOverrides: { paper: { ...glass, backgroundImage: "none" } },
    },
  },
});
