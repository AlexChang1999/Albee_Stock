// ============================================================
// CreateBotForm：建立新 Bot 的表單
// ============================================================
// props：
//   form     — 表單目前的值（{ name, strategy, symbol, trade_amount }）
//   setForm  — 更新表單值的函式
//   onSubmit — 按下「建立 Bot」時要跑的函式
//
// 觀念：這是「受控元件」（controlled component）——輸入框的值由 React state
// （form）控制，使用者打字時透過 setForm 更新 state，畫面再跟著變。

import {
  Card,
  CardContent,
  Typography,
  Box,
  TextField,
  MenuItem,
  Button,
} from "@mui/material";
import { STRATEGIES } from "../constants";

export default function CreateBotForm({ form, setForm, onSubmit }) {
  return (
    <Card sx={{ mb: 3 }}>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          建立新的 Bot
        </Typography>
        <Box
          component="form"
          onSubmit={onSubmit}
          sx={{
            display: "grid",
            gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" },
            gap: 2,
            mt: 1,
          }}
        >
          <TextField
            label="名稱"
            required
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            placeholder="例如：我的蘋果均線 Bot"
          />
          <TextField
            select
            label="策略"
            value={form.strategy}
            onChange={(e) => setForm({ ...form, strategy: e.target.value })}
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
            value={form.symbol}
            onChange={(e) => setForm({ ...form, symbol: e.target.value })}
            placeholder="例如：AAPL"
          />
          <TextField
            label="每次下單金額 (USD)"
            type="number"
            value={form.trade_amount}
            onChange={(e) => setForm({ ...form, trade_amount: e.target.value })}
          />

          {/* ----- 風控設定（選填，空白 = 不啟用該機制）----- */}
          <Typography
            variant="subtitle2"
            color="text.secondary"
            sx={{ gridColumn: { sm: "1 / -1" }, mt: 1 }}
          >
            風控設定（選填，留空表示不啟用）
          </Typography>
          <TextField
            label="止盈 %"
            type="number"
            value={form.tp}
            onChange={(e) => setForm({ ...form, tp: e.target.value })}
            helperText="漲多少就賣，例：10 = +10%"
          />
          <TextField
            label="止損 %"
            type="number"
            value={form.sl}
            onChange={(e) => setForm({ ...form, sl: e.target.value })}
            helperText="跌多少就賣，例：5 = −5%"
          />
          <TextField
            label="追蹤止損 %"
            type="number"
            value={form.trail}
            onChange={(e) => setForm({ ...form, trail: e.target.value })}
            helperText="從最高價回落多少就賣，例：3"
          />
          <TextField
            label="監測頻率（秒）"
            type="number"
            value={form.interval}
            onChange={(e) => setForm({ ...form, interval: e.target.value })}
            helperText="啟動後每幾秒檢查一次，預設 60"
          />

          <Button
            type="submit"
            variant="contained"
            sx={{ gridColumn: { sm: "1 / -1" }, justifySelf: "start" }}
          >
            建立 Bot
          </Button>
        </Box>
      </CardContent>
    </Card>
  );
}
