// ============================================================
// SidebarLayout：全站外殼（左側導覽 + 右側路由內容）
// ============================================================
// Phase 9 step-01：把原本「上方 4 個 Tabs」換成「左側 sidebar 導覽 + 路由頁」。
// 這支是常駐外殼，每換一個路由只換中間 <Outlet> 的內容；Header、側欄、
// 右側策略工作台都留著不重繪。
//
// 設計：沿用 theme.js 的 NEON 色票與深藍主題，不另立配色。
// 用 react-router 的 NavLink 做「目前所在頁」的高亮。
//
// props：
//   status   — 交易環境狀態（給 Header 與實盤警告橫幅）
//   loading  — 載入中（顯示頂部細進度條）
//   error/message/loadError — 全站操作訊息（顯示在內容上方）
//   context  — 傳給各路由頁的共享資料/動作（頁面用 useOutletContext() 取）
//   workbench — 右側策略工作台元件（暫時保留，step-08 才移除）

import { Box, Container, Alert, LinearProgress, Typography, Snackbar } from "@mui/material";
import { NavLink, Outlet } from "react-router-dom";
import Header from "./Header";
import AssistantDrawer from "./AssistantDrawer";
import { NEON } from "../theme";

// 導覽項目：依 Phase 9 README 壹節資訊架構。
// 灰底（依賴前面 phase）頁面在對應 step 落地時再逐一加進來。
const NAV_ITEMS = [
  { to: "/", label: "監控中心", end: true },
  { to: "/company", label: "公司戰情" },
  { to: "/promotions", label: "董事會核准" },
  { to: "/bot-review", label: "汰弱審查員" },
  { to: "/factors", label: "因子報表" },
  { to: "/collector", label: "市場蒐集員" },
  { to: "/political", label: "政治專討員" },
  { to: "/trades", label: "交易紀錄" },
  { to: "/backtest-runs", label: "回測歷史" },
  { to: "/presets", label: "策略方案" },
  { to: "/explorations", label: "探討檢討" },
  { to: "/decisions", label: "決策審計" },
  { to: "/evolution", label: "進化實驗室" },
  { to: "/library", label: "策略知識庫" },
  { to: "/ai-explore", label: "AI 探勘" },
  { to: "/charts", label: "K 線圖" },
  { to: "/fundamentals", label: "基本面" },
  { to: "/backtest", label: "回測工具" },
];

// 單一導覽連結：用 NavLink 的 isActive 切換高亮樣式。
function NavItem({ to, label, end }) {
  return (
    <NavLink to={to} end={end} style={{ textDecoration: "none" }}>
      {({ isActive }) => (
        <Box
          sx={{
            px: 2,
            py: 1.1,
            mb: 0.5,
            borderRadius: 2,
            cursor: "pointer",
            fontFamily: '"Manrope", sans-serif',
            fontWeight: 600,
            fontSize: 14,
            letterSpacing: "0.01em",
            color: isActive ? "#08152b" : "text.secondary",
            background: isActive ? NEON.cyan : "transparent",
            boxShadow: isActive ? "0 2px 10px rgba(77,163,255,0.3)" : "none",
            transition: "background .2s, color .2s",
            "&:hover": {
              color: isActive ? "#08152b" : "text.primary",
              background: isActive ? NEON.cyan : "rgba(77,163,255,0.1)",
            },
          }}
        >
          {label}
        </Box>
      )}
    </NavLink>
  );
}

export default function SidebarLayout({
  status,
  loading,
  error,
  message,
  onClearMessage,
  loadError,
  context,
  colorMode,
  onToggleColorMode,
}) {
  return (
    <>
      <Header status={status} />

      {/* 實盤警告橫幅：雙閘全開時才出現，提醒此刻下單會動真錢 */}
      {status?.live_armed && (
        <Alert severity="error" square sx={{ borderRadius: 0 }}>
          ⚠️ 目前是<strong>實盤模式</strong>，所有下單將動用<strong>真實資金</strong>。請務必確認。
        </Alert>
      )}

      {loading && <LinearProgress />}

      <Box sx={{ display: "flex", alignItems: "flex-start" }}>
        {/* 左側導覽 */}
        <Box
          component="nav"
          sx={{
            width: 210,
            flexShrink: 0,
            position: "sticky",
            top: 0,
            alignSelf: "flex-start",
            px: 1.5,
            py: 3,
            minHeight: "calc(100vh - 64px)",
            borderRight: "1px solid",
            borderColor: "divider",
          }}
        >
          <Typography
            sx={{
              px: 2,
              mb: 1.5,
              fontSize: 11,
              letterSpacing: "0.18em",
              textTransform: "uppercase",
              color: "text.secondary",
              fontFamily: '"IBM Plex Mono", monospace',
            }}
          >
            導覽
          </Typography>
          {NAV_ITEMS.map((item) => (
            <NavItem key={item.to} {...item} />
          ))}

          {/* 亮/暗模式切換（E1）：存 localStorage，下次開啟沿用 */}
          {onToggleColorMode && (
            <Box
              component="button"
              type="button"
              onClick={onToggleColorMode}
              aria-label="切換亮暗模式"
              sx={{
                mt: 2,
                px: 2,
                py: 1,
                width: "100%",
                textAlign: "left",
                borderRadius: 2,
                border: "1px solid",
                borderColor: "divider",
                background: "transparent",
                color: "text.secondary",
                cursor: "pointer",
                fontFamily: '"Manrope", sans-serif',
                fontWeight: 600,
                fontSize: 13,
                "&:hover": { color: "text.primary", borderColor: "primary.main" },
              }}
            >
              {colorMode === "dark" ? "☀️ 亮色模式" : "🌙 深藍模式"}
            </Box>
          )}
        </Box>

        {/* 中間路由內容 */}
        <Container
          maxWidth={false}
          sx={{
            flex: 1,
            minWidth: 0,
            py: 4,
            px: { xs: 2, md: 4 },
            animation: "albeeFadeUp .5s ease both",
          }}
        >
          {/* 錯誤常駐顯示（需要使用者看清楚並處理）；成功訊息改用下方 Snackbar */}
          {(error || loadError) && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {error || loadError}
            </Alert>
          )}

          {/* 路由頁透過 useOutletContext() 取得共享資料/動作 */}
          <Outlet context={context} />
        </Container>

      </Box>

      {/* 成功訊息：浮層 Snackbar，4 秒自動消失、不偷鍵盤焦點；role=status（aria-live polite） */}
      <Snackbar
        open={!!message}
        autoHideDuration={4000}
        onClose={onClearMessage}
        anchorOrigin={{ vertical: "bottom", horizontal: "center" }}
      >
        <Alert
          severity="success"
          variant="filled"
          role="status"
          onClose={onClearMessage}
          sx={{ width: "100%" }}
        >
          {message}
        </Alert>
      </Snackbar>

      {/* 全站思考助手抽屜（右下浮動鈕開關，取代原右側策略工作台） */}
      <AssistantDrawer />
    </>
  );
}
