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

const INK = "#e7edf7"; // 主文字：近白冷光
const INK_SOFT = "#9aa9c2"; // 次要文字：灰藍
const PANEL = "#0f1f3a"; // 面板底：深海軍藍
const LINE = "rgba(255,255,255,0.09)"; // 冷色髮絲線

// 卡片共用底樣式：深藍面板 + 冷色細邊 + 深處陰影（沉浸、不刺眼）。
const paperCard = {
  backgroundColor: PANEL,
  backgroundImage: "none",
  border: `1px solid ${LINE}`,
  borderRadius: 16,
  // 深色底用「外陰影壓深 + 內側一條極淡高光」營造面板浮起感
  boxShadow:
    "0 1px 0 rgba(255,255,255,0.04) inset, 0 16px 32px -22px rgba(0,0,0,0.7)",
  transition: "border-color .25s, box-shadow .25s, transform .25s",
};

export const theme = createTheme({
  palette: {
    mode: "dark",
    primary: { main: NEON.cyan },
    secondary: { main: NEON.magenta },
    success: { main: NEON.green },
    error: { main: NEON.red },
    warning: { main: NEON.magenta },
    // 背景透明，讓 index.css 的深藍底與冷色光暈透出來
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
            boxShadow:
              "0 1px 0 rgba(255,255,255,0.05) inset, 0 22px 40px -24px rgba(0,0,0,0.8)",
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
