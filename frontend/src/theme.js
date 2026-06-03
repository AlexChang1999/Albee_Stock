// ============================================================
// 全站主題設定（精緻淺色金融風：米白紙感 + 襯線大標 + 收斂金融色）
// ============================================================
// 重點觀念：MUI 的 components.styleOverrides 可以「一次改掉全站」
// 某種元件的長相。例如下面改了 MuiCard，整頁所有 <Card> 自動變成
// 乾淨的紙感卡片，不必逐個加 sx。這是全套換皮最省力又最一致的做法。
//
// 設計方向「精緻淺色金融」：像高級財經刊物 / 私人銀行對帳單——
//   乾淨白卡 + 髮絲線邊框 + 大方留白 + 襯線標題 + 一個收斂的綠色主調。
//   刻意拿掉霓虹發光與玻璃模糊，改走「安靜、有質感」的高級感。

import { createTheme } from "@mui/material/styles";

// 色票（精緻淺色金融）。
// 注意：沿用既有 NEON 這個匯出名稱與鍵名（cyan/magenta/green/red），
// 讓 Header、StrategyWorkbench 等既有 import 不用改就能換上新色：
//   cyan    -> 主色（森林綠）       magenta -> 點綴（黃銅金）
//   green   -> 上漲/獲利            red     -> 下跌/虧損
export const NEON = {
  cyan: "#1f6f54", // 主色：森林綠（行動、上漲、focus）
  magenta: "#b0883a", // 點綴：黃銅金（強調、收藏、EV 冠軍）
  green: "#1f7a5a", // 獲利綠
  red: "#b23b32", // 虧損磚紅
};

const INK = "#1c2230"; // 主文字
const INK_SOFT = "#5b6573"; // 次要文字
const LINE = "rgba(28,34,48,0.10)"; // 髮絲線

// 卡片共用底樣式：純白紙感 + 髮絲線 + 柔和雙層陰影（無玻璃模糊）。
// 高級感來自「乾淨 + 細邊 + 大留白」，不是發光特效。
const paperCard = {
  backgroundColor: "#ffffff",
  backgroundImage: "none",
  border: `1px solid ${LINE}`,
  borderRadius: 16,
  // 雙層陰影：近處一條極淡的線稿陰影 + 遠處柔和的浮起陰影
  boxShadow:
    "0 1px 2px rgba(28,34,48,0.04), 0 12px 28px -18px rgba(28,34,48,0.22)",
  transition: "border-color .25s, box-shadow .25s, transform .25s",
};

export const theme = createTheme({
  palette: {
    mode: "light",
    primary: { main: NEON.cyan },
    secondary: { main: NEON.magenta },
    success: { main: NEON.green },
    error: { main: NEON.red },
    warning: { main: "#b0883a" },
    // 背景透明，讓 index.css 的米白底與暖色光暈透出來
    background: { default: "transparent", paper: "#ffffff" },
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
    // 卡片：白紙感，滑入時邊框轉深綠、陰影加深並輕輕浮起
    MuiCard: {
      styleOverrides: {
        root: {
          ...paperCard,
          "&:hover": {
            borderColor: "rgba(31,111,84,0.28)",
            boxShadow:
              "0 1px 2px rgba(28,34,48,0.05), 0 18px 36px -20px rgba(28,34,48,0.28)",
          },
        },
      },
    },
    // Paper（outlined 變體用在 Bot 卡片、表格容器）：同白紙風
    MuiPaper: {
      styleOverrides: {
        outlined: {
          ...paperCard,
          "&:hover": {
            borderColor: "rgba(31,111,84,0.24)",
          },
        },
      },
    },
    // 實心按鈕：實心深綠（不再霓虹漸層），hover 加深 + 輕微浮起
    MuiButton: {
      styleOverrides: {
        root: { borderRadius: 10 },
        containedPrimary: {
          background: NEON.cyan,
          color: "#ffffff",
          fontWeight: 600,
          boxShadow: "0 2px 8px rgba(31,111,84,0.22)",
          "&:hover": {
            background: "#1a5d47",
            boxShadow: "0 4px 14px rgba(31,111,84,0.3)",
          },
        },
        outlinedPrimary: {
          borderColor: "rgba(31,111,84,0.4)",
          color: NEON.cyan,
          "&:hover": {
            borderColor: NEON.cyan,
            background: "rgba(31,111,84,0.05)",
          },
        },
      },
    },
    // 輸入框：白底，聚焦時深綠細框 + 淡光圈
    MuiOutlinedInput: {
      styleOverrides: {
        root: {
          background: "#ffffff",
          borderRadius: 10,
          "& .MuiOutlinedInput-notchedOutline": {
            borderColor: LINE,
          },
          "&:hover .MuiOutlinedInput-notchedOutline": {
            borderColor: "rgba(31,111,84,0.45)",
          },
          "&.Mui-focused .MuiOutlinedInput-notchedOutline": {
            borderColor: NEON.cyan,
            boxShadow: "0 0 0 3px rgba(31,111,84,0.1)",
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
    // 分頁指示線：深綠細線
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
    // 彈出視窗：白紙感
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
