// ============================================================
// Albee Stock 主畫面（使用 MUI 元件）
// ============================================================
// 四個區塊：1.帳戶資訊 2.建立 Bot 3.Bot 列表 4.交易紀錄
// 邏輯跟之前一樣，只是改用 Material UI 的現成元件讓畫面更漂亮。

import { useState, useEffect } from "react";
import { api } from "./api";
import {
  AppBar,
  Toolbar,
  Typography,
  Container,
  Card,
  CardContent,
  Box,
  TextField,
  MenuItem,
  Button,
  Alert,
  Chip,
  Table,
  TableHead,
  TableBody,
  TableRow,
  TableCell,
  TableContainer,
  Paper,
  CssBaseline,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  IconButton,
  Tooltip,
  Stack,
  Tabs,
  Tab,
} from "@mui/material";
import { createTheme, ThemeProvider } from "@mui/material/styles";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import StopIcon from "@mui/icons-material/Stop";
import RefreshIcon from "@mui/icons-material/Refresh";
import EditIcon from "@mui/icons-material/Edit";
import DeleteIcon from "@mui/icons-material/Delete";
import TradingViewChart from "./TradingViewChart";
import BotAvatar from "./BotAvatar";

// 建立一個主題（主色用藍色）
const theme = createTheme({
  palette: { primary: { main: "#2563eb" } },
});

// 可選的策略清單（對應後端的策略註冊表）
const STRATEGIES = [
  { value: "ma_crossover", label: "均線交叉" },
  { value: "rsi", label: "RSI" },
  { value: "macd", label: "MACD" },
  { value: "bollinger", label: "布林通道" },
  { value: "donchian", label: "唐奇安通道突破" },
  { value: "stochastic", label: "KD 隨機指標" },
  { value: "momentum", label: "動量" },
];

// 小元件：顯示一個帳戶數字（標籤 + 數值）
function Stat({ label, value }) {
  return (
    <Box>
      <Typography variant="caption" color="text.secondary">
        {label}
      </Typography>
      <Typography variant="h6">{value}</Typography>
    </Box>
  );
}

function App() {
  const [account, setAccount] = useState(null);
  const [bots, setBots] = useState([]);
  const [trades, setTrades] = useState([]);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  // 圖表目前顯示的股票（chartSymbol）與輸入框的暫存值（symbolInput）
  const [chartSymbol, setChartSymbol] = useState("AAPL");
  const [symbolInput, setSymbolInput] = useState("AAPL");

  // 目前分頁：0 = 儀表板，1 = K 線圖
  const [tab, setTab] = useState(0);

  // 回測相關狀態
  const [btForm, setBtForm] = useState({
    strategy: "ma_crossover",
    symbol: "AAPL",
    days: 365,
    initial_cash: 10000,
  });
  const [btResult, setBtResult] = useState(null); // 回測結果
  const [btLoading, setBtLoading] = useState(false); // 是否回測中

  const [form, setForm] = useState({
    name: "",
    strategy: "ma_crossover",
    symbol: "",
    trade_amount: 1000,
  });

  // 正在編輯的 Bot（null = 沒有打開編輯視窗）
  const [editBot, setEditBot] = useState(null);

  // 從後端載入所有資料
  async function loadAll() {
    try {
      setAccount(await api.getAccount());
    } catch (e) {
      setError("無法取得帳戶資料（後端有啟動嗎？API 金鑰正確嗎？）：" + e.message);
    }
    try {
      setBots(await api.getBots());
      setTrades(await api.getTrades());
    } catch (e) {
      setError(e.message);
    }
  }

  useEffect(() => {
    loadAll();
  }, []);

  // 送出建立 Bot
  async function handleCreate(e) {
    e.preventDefault();
    setError("");
    setMessage("");
    try {
      await api.createBot({
        name: form.name,
        strategy: form.strategy,
        symbol: form.symbol.toUpperCase(),
        params: {},
        trade_amount: Number(form.trade_amount),
      });
      setMessage(`已建立 Bot：${form.name}`);
      setForm({ ...form, name: "", symbol: "" });
      loadAll();
    } catch (e) {
      setError(e.message);
    }
  }

  // 手動執行某個 Bot
  async function handleRun(id) {
    setError("");
    setMessage("");
    try {
      const r = await api.runBot(id);
      setMessage(`${r.message}（買賣訊號請看後端終端機的 log）`);
      loadAll();
    } catch (e) {
      setError(e.message);
    }
  }

  // 執行回測
  async function handleBacktest() {
    setError("");
    setBtResult(null);
    setBtLoading(true); // 開始載入（按鈕會變「回測中…」）
    try {
      const r = await api.runBacktest({
        strategy: btForm.strategy,
        symbol: btForm.symbol.toUpperCase(),
        params: {},
        days: Number(btForm.days),
        initial_cash: Number(btForm.initial_cash),
      });
      setBtResult(r);
    } catch (e) {
      setError(e.message);
    } finally {
      setBtLoading(false); // 不論成功失敗都結束載入
    }
  }

  // 啟動 / 停止 Bot（依目前狀態切換）
  async function handleToggleActive(bot) {
    setError("");
    setMessage("");
    try {
      if (bot.is_active) {
        await api.stopBot(bot.id);
        setMessage(`已停止 Bot：${bot.name}`);
      } else {
        await api.startBot(bot.id);
        setMessage(`已啟動 Bot：${bot.name}（每 60 秒檢查一次）`);
      }
      loadAll();
    } catch (e) {
      setError(e.message);
    }
  }

  // 刪除 Bot（先跳出確認）
  async function handleDelete(bot) {
    if (!window.confirm(`確定要刪除「${bot.name}」嗎？此動作無法復原。`)) return;
    setError("");
    setMessage("");
    try {
      await api.deleteBot(bot.id);
      setMessage(`已刪除 Bot：${bot.name}`);
      loadAll();
    } catch (e) {
      setError(e.message);
    }
  }

  // 儲存編輯（送出 PUT）
  async function handleEditSave() {
    setError("");
    setMessage("");
    try {
      await api.updateBot(editBot.id, {
        name: editBot.name,
        strategy: editBot.strategy,
        symbol: editBot.symbol.toUpperCase(),
        params: {},
        trade_amount: Number(editBot.trade_amount),
      });
      setMessage(`已更新 Bot：${editBot.name}`);
      setEditBot(null); // 關閉視窗
      loadAll();
    } catch (e) {
      setError(e.message);
    }
  }

  return (
    <ThemeProvider theme={theme}>
      {/* CssBaseline：統一各瀏覽器的預設樣式 */}
      <CssBaseline />

      {/* 頂部標題列 */}
      <AppBar position="static">
        <Toolbar>
          <Typography variant="h6">🤖 Albee Stock 交易機器人</Typography>
        </Toolbar>
      </AppBar>

      <Container maxWidth={tab === 1 ? "lg" : "md"} sx={{ py: 4 }}>
        {/* 訊息提示 */}
        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}
        {message && (
          <Alert severity="success" sx={{ mb: 2 }}>
            {message}
          </Alert>
        )}

        {/* 分頁切換 */}
        <Tabs value={tab} onChange={(e, v) => setTab(v)} sx={{ mb: 3 }}>
          <Tab label="儀表板" />
          <Tab label="K 線圖" />
        </Tabs>

        {/* ===== 儀表板分頁 ===== */}
        {tab === 0 && (
          <Box>

        {/* 1. 帳戶資訊 */}
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              帳戶資訊
            </Typography>
            {account ? (
              <Box
                sx={{
                  display: "grid",
                  gridTemplateColumns: { xs: "1fr 1fr", sm: "repeat(4, 1fr)" },
                  gap: 2,
                }}
              >
                <Stat label="狀態" value={account.status} />
                <Stat
                  label="現金"
                  value={`$${Number(account.cash).toLocaleString()}`}
                />
                <Stat
                  label="購買力"
                  value={`$${Number(account.buying_power).toLocaleString()}`}
                />
                <Stat
                  label="總值"
                  value={`$${Number(account.portfolio_value).toLocaleString()}`}
                />
              </Box>
            ) : (
              <Typography color="text.secondary">
                載入中…（若一直沒出現，請確認後端已啟動）
              </Typography>
            )}
          </CardContent>
        </Card>

        {/* 2. 建立 Bot */}
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              建立新的 Bot
            </Typography>
            <Box
              component="form"
              onSubmit={handleCreate}
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
                onChange={(e) =>
                  setForm({ ...form, trade_amount: e.target.value })
                }
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

        {/* 3. Bot 列表 */}
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
              <TableContainer component={Paper} variant="outlined">
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>ID</TableCell>
                      <TableCell>名稱</TableCell>
                      <TableCell>策略</TableCell>
                      <TableCell>股票</TableCell>
                      <TableCell>金額</TableCell>
                      <TableCell>狀態</TableCell>
                      <TableCell>操作</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {bots.map((b) => (
                      <TableRow key={b.id}>
                        <TableCell>{b.id}</TableCell>
                        <TableCell>
                          <Box
                            sx={{
                              display: "flex",
                              alignItems: "center",
                              gap: 1,
                            }}
                          >
                            <BotAvatar
                              seed={`${b.id}-${b.name}`}
                              size={36}
                              active={b.is_active}
                            />
                            {b.name}
                          </Box>
                        </TableCell>
                        <TableCell>{b.strategy}</TableCell>
                        <TableCell>{b.symbol}</TableCell>
                        <TableCell>${b.trade_amount}</TableCell>
                        <TableCell>
                          <Chip
                            size="small"
                            color={b.is_active ? "success" : "default"}
                            label={b.is_active ? "啟用" : "停用"}
                          />
                        </TableCell>
                        <TableCell>
                          <Stack direction="row" spacing={0.5}>
                            <Tooltip title={b.is_active ? "停止" : "啟動"}>
                              <IconButton
                                size="small"
                                color={b.is_active ? "warning" : "success"}
                                onClick={() => handleToggleActive(b)}
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
                                onClick={() => handleRun(b.id)}
                              >
                                <RefreshIcon fontSize="small" />
                              </IconButton>
                            </Tooltip>
                            <Tooltip title="編輯">
                              <IconButton
                                size="small"
                                onClick={() => setEditBot({ ...b })}
                              >
                                <EditIcon fontSize="small" />
                              </IconButton>
                            </Tooltip>
                            <Tooltip title="刪除">
                              <IconButton
                                size="small"
                                color="error"
                                onClick={() => handleDelete(b)}
                              >
                                <DeleteIcon fontSize="small" />
                              </IconButton>
                            </Tooltip>
                          </Stack>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            )}
          </CardContent>
        </Card>

        {/* 策略回測 */}
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              策略回測
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              用歷史資料模擬策略表現，跟「單純買進持有」比較，看策略有沒有效。
            </Typography>
            <Box
              sx={{
                display: "grid",
                gridTemplateColumns: { xs: "1fr 1fr", sm: "repeat(4, 1fr)" },
                gap: 2,
                mb: 2,
              }}
            >
              <TextField
                select
                label="策略"
                value={btForm.strategy}
                onChange={(e) =>
                  setBtForm({ ...btForm, strategy: e.target.value })
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
                value={btForm.symbol}
                onChange={(e) => setBtForm({ ...btForm, symbol: e.target.value })}
              />
              <TextField
                label="回測天數"
                type="number"
                value={btForm.days}
                onChange={(e) => setBtForm({ ...btForm, days: e.target.value })}
              />
              <TextField
                label="初始資金 (USD)"
                type="number"
                value={btForm.initial_cash}
                onChange={(e) =>
                  setBtForm({ ...btForm, initial_cash: e.target.value })
                }
              />
            </Box>
            <Button
              variant="contained"
              onClick={handleBacktest}
              disabled={btLoading}
            >
              {btLoading ? "回測中…" : "開始回測"}
            </Button>

            {/* 回測結果 */}
            {btResult && (
              <Box sx={{ mt: 3 }}>
                <Box
                  sx={{
                    display: "grid",
                    gridTemplateColumns: {
                      xs: "1fr 1fr",
                      sm: "repeat(4, 1fr)",
                    },
                    gap: 2,
                  }}
                >
                  <Stat
                    label="策略總報酬"
                    value={`${btResult.total_return_pct}%`}
                  />
                  <Stat
                    label="買進持有對照"
                    value={`${btResult.buy_and_hold_pct}%`}
                  />
                  <Stat
                    label="最大回撤"
                    value={`${btResult.max_drawdown_pct}%`}
                  />
                  <Stat label="勝率" value={`${btResult.win_rate_pct}%`} />
                  <Stat
                    label="最終資產"
                    value={`$${btResult.final_equity.toLocaleString()}`}
                  />
                  <Stat label="交易次數" value={btResult.num_trades} />
                  <Stat label="完整買賣" value={btResult.num_round_trips} />
                  <Stat label="資料天數" value={btResult.data_points} />
                </Box>

                {/* 一句話解讀 */}
                <Alert
                  severity={
                    btResult.total_return_pct >= btResult.buy_and_hold_pct
                      ? "success"
                      : "info"
                  }
                  sx={{ mt: 2 }}
                >
                  {btResult.total_return_pct >= btResult.buy_and_hold_pct
                    ? "👍 這次策略表現優於「單純買進持有」。"
                    : "這次策略跑輸「單純買進持有」，可以調整參數或換策略再試試。"}
                </Alert>

                {/* 交易明細 */}
                {btResult.trades.length > 0 && (
                  <TableContainer
                    component={Paper}
                    variant="outlined"
                    sx={{ mt: 2 }}
                  >
                    <Table size="small">
                      <TableHead>
                        <TableRow>
                          <TableCell>日期</TableCell>
                          <TableCell>買/賣</TableCell>
                          <TableCell>價格</TableCell>
                          <TableCell>盈虧</TableCell>
                          <TableCell>原因</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {btResult.trades.map((t, idx) => (
                          <TableRow key={idx}>
                            <TableCell>{t.date}</TableCell>
                            <TableCell>
                              {t.side === "buy" ? "買進" : "賣出"}
                            </TableCell>
                            <TableCell>${t.price}</TableCell>
                            <TableCell
                              sx={{
                                color:
                                  t.profit > 0
                                    ? "success.main"
                                    : t.profit < 0
                                    ? "error.main"
                                    : "text.secondary",
                              }}
                            >
                              {t.profit !== undefined ? `$${t.profit}` : "-"}
                            </TableCell>
                            <TableCell>{t.reason}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </TableContainer>
                )}
              </Box>
            )}
          </CardContent>
        </Card>

        {/* 4. 交易紀錄 */}
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              交易紀錄（{trades.length}）
            </Typography>
            {trades.length === 0 ? (
              <Typography color="text.secondary">
                目前還沒有任何交易紀錄。
              </Typography>
            ) : (
              <TableContainer component={Paper} variant="outlined">
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>時間</TableCell>
                      <TableCell>股票</TableCell>
                      <TableCell>買/賣</TableCell>
                      <TableCell>股數</TableCell>
                      <TableCell>價格</TableCell>
                      <TableCell>原因</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {trades.map((t) => (
                      <TableRow key={t.id}>
                        <TableCell>
                          {new Date(t.created_at).toLocaleString()}
                        </TableCell>
                        <TableCell>{t.symbol}</TableCell>
                        <TableCell>{t.side === "buy" ? "買進" : "賣出"}</TableCell>
                        <TableCell>{t.qty}</TableCell>
                        <TableCell>${t.price}</TableCell>
                        <TableCell>{t.reason}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            )}
          </CardContent>
        </Card>
          </Box>
        )}

        {/* ===== K 線圖分頁 ===== */}
        {tab === 1 && (
          <Box>
            <Box sx={{ display: "flex", gap: 1, mb: 2 }}>
              <TextField
                size="small"
                label="股票代號"
                value={symbolInput}
                onChange={(e) => setSymbolInput(e.target.value)}
                placeholder="例如：AAPL、TSLA、NVDA"
              />
              <Button
                variant="contained"
                onClick={() => setChartSymbol(symbolInput.toUpperCase())}
              >
                載入圖表
              </Button>
            </Box>
            {/* 可拖拉調整大小的圖表容器（拉右下角） */}
            <Box
              sx={{
                resize: "vertical",
                overflow: "hidden",
                height: "75vh",
                minHeight: 320,
                border: "1px solid",
                borderColor: "divider",
                borderRadius: 1,
              }}
            >
              <TradingViewChart symbol={chartSymbol} height="100%" />
            </Box>
            <Typography variant="caption" color="text.secondary">
              提示：拖曳圖表框的右下角可調整高度。
            </Typography>
          </Box>
        )}
      </Container>

      {/* 編輯 Bot 的彈出視窗 */}
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
                onChange={(e) =>
                  setEditBot({ ...editBot, name: e.target.value })
                }
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
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEditBot(null)}>取消</Button>
          <Button variant="contained" onClick={handleEditSave}>
            儲存
          </Button>
        </DialogActions>
      </Dialog>
    </ThemeProvider>
  );
}

export default App;
