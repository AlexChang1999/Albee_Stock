// ============================================================
// EditBotDialog：編輯 Bot 的彈出視窗
// ============================================================
// props：
//   editBot    — 正在編輯的 Bot 物件（null = 視窗關閉）
//   setEditBot — 更新編輯中的值 / 關閉視窗（傳 null 即關閉）
//   onSave     — 按下「儲存」時要跑的函式
//
// 觀念：open 用 !!editBot——把物件/null 轉成 true/false。
// 有在編輯（物件）就開窗，沒有（null）就關窗。

import {
  Box,
  Typography,
  TextField,
  MenuItem,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
} from "@mui/material";
import { STRATEGIES } from "../constants";

export default function EditBotDialog({ editBot, setEditBot, onSave }) {
  return (
    <Dialog
      open={!!editBot}
      onClose={() => setEditBot(null)}
      fullWidth
      maxWidth="xs"
    >
      <DialogTitle>編輯 Bot</DialogTitle>
      <DialogContent>
        {editBot && (
          <Box sx={{ display: "grid", gap: 2, mt: 1 }}>
            <TextField
              label="名稱"
              value={editBot.name}
              onChange={(e) => setEditBot({ ...editBot, name: e.target.value })}
            />
            <TextField
              select
              label="策略"
              value={editBot.strategy}
              onChange={(e) =>
                setEditBot({ ...editBot, strategy: e.target.value })
              }
            >
              {STRATEGIES.map((s) => (
                <MenuItem key={s.value} value={s.value}>
                  {s.label}
                </MenuItem>
              ))}
            </TextField>
            <TextField
              label="股票代號"
              value={editBot.symbol}
              onChange={(e) =>
                setEditBot({ ...editBot, symbol: e.target.value })
              }
            />
            <TextField
              label="每次下單金額 (USD)"
              type="number"
              value={editBot.trade_amount}
              onChange={(e) =>
                setEditBot({ ...editBot, trade_amount: e.target.value })
              }
            />

            {/* ----- 風控設定（選填，空白 = 不啟用）----- */}
            <Typography variant="subtitle2" color="text.secondary">
              風控設定（選填，留空表示不啟用）
            </Typography>
            <TextField
              label="止盈 %"
              type="number"
              value={editBot.tp ?? ""}
              onChange={(e) => setEditBot({ ...editBot, tp: e.target.value })}
            />
            <TextField
              label="止損 %"
              type="number"
              value={editBot.sl ?? ""}
              onChange={(e) => setEditBot({ ...editBot, sl: e.target.value })}
            />
            <TextField
              label="追蹤止損 %"
              type="number"
              value={editBot.trail ?? ""}
              onChange={(e) => setEditBot({ ...editBot, trail: e.target.value })}
            />
            <TextField
              label="監測頻率（秒）"
              type="number"
              value={editBot.interval ?? 60}
              onChange={(e) =>
                setEditBot({ ...editBot, interval: e.target.value })
              }
            />
          </Box>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={() => setEditBot(null)}>取消</Button>
        <Button variant="contained" onClick={onSave}>
          儲存
        </Button>
      </DialogActions>
    </Dialog>
  );
}
