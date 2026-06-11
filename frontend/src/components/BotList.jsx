// ============================================================
// BotList：Bot 卡片網格（每個 Bot 一張卡，含頭像、績效、操作鈕）
// ============================================================
// props：
//   bots     — Bot 陣列
//   onToggle — 啟動/停止某個 Bot（傳整個 bot 物件）
//   onRun    — 立刻執行一次（傳 bot.id）
//   onEdit   — 打開編輯視窗（傳整個 bot 物件）
//   onDelete — 刪除（傳整個 bot 物件）

import {
  Card,
  CardContent,
  Typography,
  Box,
  Chip,
  Paper,
  IconButton,
  Tooltip,
  Stack,
  Skeleton,
} from "@mui/material";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import StopIcon from "@mui/icons-material/Stop";
import RefreshIcon from "@mui/icons-material/Refresh";
import EditIcon from "@mui/icons-material/Edit";
import DeleteIcon from "@mui/icons-material/Delete";
import ReceiptLongIcon from "@mui/icons-material/ReceiptLong";
import BotAvatar from "../BotAvatar";
import BotActivityStatus, { ActivityKeyframes } from "./BotActivityStatus";
import { statRows, formatCheckedAgo, holdingText } from "../utils/botStats";

export default function BotList({
  bots,
  loading = false,
  onToggle,
  onRun,
  onEdit,
  onDelete,
  onShowDecisions,
  activityByBot = null, // useBotActivity 的即時活動（WS 沒連上時為 null → 不顯示活動條）
}) {
  return (
    <Card sx={{ mb: 3 }}>
      {/* 活動動畫的 keyframes 全域註冊一次（各卡片共用） */}
      <ActivityKeyframes />
      <CardContent>
        <Typography variant="h6" gutterBottom>
          Bot 列表（{bots.length}）
        </Typography>
        {loading && bots.length === 0 ? (
          // Skeleton 載入態（E3）：先畫卡片灰塊佔位，分得清「載入中」與「真的沒 Bot」
          <Box
            sx={{
              display: "grid",
              gridTemplateColumns: { xs: "1fr", sm: "repeat(2, 1fr)", md: "repeat(4, 1fr)" },
              gap: 2,
            }}
            aria-label="Bot 列表載入中"
          >
            {[0, 1, 2, 3].map((i) => (
              <Paper key={i} variant="outlined" sx={{ p: 2 }}>
                <Stack direction="row" spacing={1.5} alignItems="center" sx={{ mb: 1 }}>
                  <Skeleton variant="circular" width={40} height={40} />
                  <Skeleton width="60%" height={24} />
                </Stack>
                <Skeleton width="80%" />
                <Skeleton width="50%" />
              </Paper>
            ))}
          </Box>
        ) : bots.length === 0 ? (
          <Typography color="text.secondary">
            還沒有任何 Bot，先用上面的表單建立一個吧！
          </Typography>
        ) : (
          <Box
            sx={{
              display: "grid",
              gridTemplateColumns: {
                xs: "1fr",
                sm: "repeat(2, 1fr)",
                md: "repeat(4, 1fr)",
              },
              gap: 2,
            }}
          >
            {bots.map((b) => (
              <Paper
                key={b.id}
                variant="outlined"
                sx={{
                  p: 2,
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  gap: 1,
                }}
              >
                {/* 抓數據中 → 頭像外圈跟著脈衝（真事件驅動，不是裝飾） */}
                <Box
                  sx={
                    activityByBot?.[b.id]?.phase === "fetch_data"
                      ? { borderRadius: "50%", animation: "bot-pulse 1s ease-out infinite" }
                      : undefined
                  }
                >
                  <BotAvatar
                    seed={`${b.id}-${b.name}`}
                    size={56}
                    active={b.is_active}
                  />
                </Box>
                <Typography
                  variant="subtitle2"
                  noWrap
                  title={b.name}
                  sx={{ maxWidth: "100%" }}
                >
                  {b.name}
                </Typography>
                <Chip
                  size="small"
                  color={b.is_active ? "success" : "default"}
                  label={b.is_active ? "啟用" : "停用"}
                />
                <Typography variant="caption" color="text.secondary" noWrap>
                  {b.strategy} · {b.symbol} · ${b.trade_amount}
                </Typography>

                {/* 監聽狀態：持倉/空手 + 最後檢查時間（確認排程真的在動） */}
                <Typography variant="caption" color="text.secondary" noWrap>
                  {holdingText(b.peak_price)} · {formatCheckedAgo(b.last_checked_at)}
                </Typography>

                {/* 即時活動條：此刻在抓數據/計算/決策/倒數/失聯（WS 真事件驅動） */}
                <BotActivityStatus activity={activityByBot?.[b.id]} />

                {/* 績效指標（依該 Bot 的真實交易紀錄計算；沒交易時顯示 "-"） */}
                <Box
                  sx={{
                    display: "grid",
                    gridTemplateColumns: "1fr 1fr",
                    gap: 0.5,
                    width: "100%",
                    mt: 0.5,
                  }}
                >
                  {statRows(b.stats).map(([label, val, color]) => (
                    <Box key={label} sx={{ textAlign: "center" }}>
                      <Typography
                        variant="caption"
                        color="text.secondary"
                        display="block"
                      >
                        {label}
                      </Typography>
                      <Typography
                        variant="body2"
                        fontWeight={600}
                        color={color || "text.primary"}
                      >
                        {val}
                      </Typography>
                    </Box>
                  ))}
                </Box>

                {/* 操作 */}
                <Stack direction="row" spacing={0.5} sx={{ mt: 0.5 }}>
                  {/* 圖示鈕都補 aria-label：Tooltip 只在 hover/focus 時提供無障礙名稱，
                      平時螢幕報讀會讀成「button」讀不出用途，故額外標明（含 Bot 名）。 */}
                  <Tooltip title={b.is_active ? "停止" : "啟動"}>
                    <IconButton
                      size="small"
                      color={b.is_active ? "warning" : "success"}
                      aria-label={`${b.is_active ? "停止" : "啟動"} ${b.name}`}
                      onClick={() => onToggle(b)}
                    >
                      {b.is_active ? (
                        <StopIcon fontSize="small" />
                      ) : (
                        <PlayArrowIcon fontSize="small" />
                      )}
                    </IconButton>
                  </Tooltip>
                  <Tooltip title="執行一次">
                    <IconButton
                      size="small"
                      aria-label={`立即執行一次 ${b.name}`}
                      onClick={() => onRun(b.id)}
                    >
                      <RefreshIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                  <Tooltip title="決策軌跡">
                    <IconButton
                      size="small"
                      aria-label={`查看 ${b.name} 的決策軌跡`}
                      onClick={() => onShowDecisions(b)}
                    >
                      <ReceiptLongIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                  <Tooltip title="編輯">
                    <IconButton
                      size="small"
                      aria-label={`編輯 ${b.name}`}
                      onClick={() => onEdit({ ...b })}
                    >
                      <EditIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                  <Tooltip title="刪除">
                    <IconButton
                      size="small"
                      color="error"
                      aria-label={`刪除 ${b.name}`}
                      onClick={() => onDelete(b)}
                    >
                      <DeleteIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                </Stack>
              </Paper>
            ))}
          </Box>
        )}
      </CardContent>
    </Card>
  );
}
