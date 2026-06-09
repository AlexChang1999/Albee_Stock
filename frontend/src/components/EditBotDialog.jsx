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
//
// 表單品質（UI/UX 規則 §8）：必填欄標紅星（required）、即時驗證、
// 錯誤訊息就在欄位下方（helperText）、有錯時停用「儲存」鈕，避免送出無效資料。

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
  // ----- 即時驗證：必填欄空白 / 數值不合理時標紅 + 提示，並停用「儲存」-----
  const v = editBot || {};
  const nameErr = !String(v.name ?? "").trim();
  const symbolErr = !String(v.symbol ?? "").trim();
  const amountNum = Number(v.trade_amount);
  const amountErr =
    v.trade_amount === "" ||
    v.trade_amount == null ||
    !Number.isFinite(amountNum) ||
    amountNum <= 0;
  // 風控百分比為選填；一旦填了就必須是 0–100 之間的正數
  const pctErr = (val) => {
    if (val === "" || val == null) return false;
    const n = Number(val);
    return !Number.isFinite(n) || n <= 0 || n >= 100;
  };
  const tpErr = pctErr(v.tp);
  const slErr = pctErr(v.sl);
  const trailErr = pctErr(v.trail);
  // 監測頻率選填；填了需 >= 1 秒
  const intervalErr =
    v.interval !== "" &&
    v.interval != null &&
    (!Number.isFinite(Number(v.interval)) || Number(v.interval) < 1);
  const hasError =
    nameErr || symbolErr || amountErr || tpErr || slErr || trailErr || intervalErr;

  // 百分比欄位的常駐提示（沒錯時顯示，讓使用者知道規則）
  const PCT_HELP = "選填，留空＝不啟用；填則需 0–100";

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
              required
              value={editBot.name}
              error={nameErr}
              helperText={nameErr ? "名稱不能空白" : " "}
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
              required
              value={editBot.symbol}
              error={symbolErr}
              helperText={symbolErr ? "請填股票代號" : " "}
              onChange={(e) =>
                setEditBot({ ...editBot, symbol: e.target.value })
              }
            />
            <TextField
              label="每次下單金額 (USD)"
              type="number"
              required
              value={editBot.trade_amount}
              error={amountErr}
              helperText={amountErr ? "請填大於 0 的金額" : " "}
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
              error={tpErr}
              helperText={tpErr ? "請填 0 到 100 之間的百分比" : PCT_HELP}
              onChange={(e) => setEditBot({ ...editBot, tp: e.target.value })}
            />
            <TextField
              label="止損 %"
              type="number"
              value={editBot.sl ?? ""}
              error={slErr}
              helperText={slErr ? "請填 0 到 100 之間的百分比" : PCT_HELP}
              onChange={(e) => setEditBot({ ...editBot, sl: e.target.value })}
            />
            <TextField
              label="追蹤止損 %"
              type="number"
              value={editBot.trail ?? ""}
              error={trailErr}
              helperText={trailErr ? "請填 0 到 100 之間的百分比" : PCT_HELP}
              onChange={(e) => setEditBot({ ...editBot, trail: e.target.value })}
            />
            <TextField
              label="監測頻率（秒）"
              type="number"
              value={editBot.interval ?? 60}
              error={intervalErr}
              helperText={intervalErr ? "請填 ≥ 1 的秒數" : " "}
              onChange={(e) =>
                setEditBot({ ...editBot, interval: e.target.value })
              }
            />
          </Box>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={() => setEditBot(null)}>取消</Button>
        <Button variant="contained" onClick={onSave} disabled={hasError}>
          儲存
        </Button>
      </DialogActions>
    </Dialog>
  );
}
