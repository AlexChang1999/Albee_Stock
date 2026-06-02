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
} from "@mui/material";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import StopIcon from "@mui/icons-material/Stop";
import RefreshIcon from "@mui/icons-material/Refresh";
import EditIcon from "@mui/icons-material/Edit";
import DeleteIcon from "@mui/icons-material/Delete";
import BotAvatar from "../BotAvatar";
import { statRows, formatCheckedAgo, holdingText } from "../utils/botStats";

export default function BotList({ bots, onToggle, onRun, onEdit, onDelete }) {
  return (
    <Card sx={{ mb: 3 }}>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          Bot 列表（{bots.length}）
        </Typography>
        {bots.length === 0 ? (
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
                <BotAvatar
                  seed={`${b.id}-${b.name}`}
                  size={56}
                  active={b.is_active}
                />
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
                  <Tooltip title={b.is_active ? "停止" : "啟動"}>
                    <IconButton
                      size="small"
                      color={b.is_active ? "warning" : "success"}
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
                    <IconButton size="small" onClick={() => onRun(b.id)}>
                      <RefreshIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                  <Tooltip title="編輯">
                    <IconButton size="small" onClick={() => onEdit({ ...b })}>
                      <EditIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                  <Tooltip title="刪除">
                    <IconButton
                      size="small"
                      color="error"
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
