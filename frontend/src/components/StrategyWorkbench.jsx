// ============================================================
// StrategyWorkbench：右側「策略工作台」面板（Phase 5）
// ============================================================
// 一個自包含的側邊面板，自己管自己的資料流（讀寫 presets / backtest-runs / chat）。
// App 只要把它放在版面右側即可，不必接一堆 props。
//
// 功能分四區：
//   1. 策略方案：列出 presets，可新增 / 改名 / 調參數 / 收藏 / 刪除
//   2. 一鍵回測（Python）：選方案 → 按「跑回測」→ 結果卡（★EV 當頭條）
//   3. 回測歷史 / 好策略榜：依 EV 由高到低排序，可收藏標星
//   4. Claude 助手：聊天區 + 每筆回測旁「總結這次錯在哪」按鈕（步驟 4 為 stub）
//
// 兩個互動細節：
//   - 可收合：收合後只剩一條細邊條 + 展開鈕。
//   - 可橫向拉寬：面板左緣有一條 6px 拖曳把手，自製 mousedown/move/up，
//     寬度 clamp 在 320~720，記到 localStorage（下次打開記得上次寬度）。

import { useState, useEffect, useCallback, useRef } from "react";
import {
  Box,
  Paper,
  Typography,
  TextField,
  MenuItem,
  Button,
  IconButton,
  Stack,
  Chip,
  Alert,
  CircularProgress,
  Tooltip,
} from "@mui/material";
import { STRATEGIES } from "../constants";
import { NEON } from "../theme";
import { api } from "../api";

// localStorage 的鍵名（存面板寬度）
const WIDTH_KEY = "workbench_width";
const MIN_W = 320;
const MAX_W = 720;

// 把策略代號轉成中文標籤
function strategyLabel(key) {
  return STRATEGIES.find((s) => s.value === key)?.label || key;
}

export default function StrategyWorkbench() {
  // ----- 版面狀態：寬度 + 收合 -----
  const [width, setWidth] = useState(() => {
    const saved = Number(localStorage.getItem(WIDTH_KEY));
    return saved >= MIN_W && saved <= MAX_W ? saved : 380;
  });
  const [collapsed, setCollapsed] = useState(false);

  // 拖曳把手：面板在右側，往左拖（clientX 變小）= 變寬
  // widthRef 讓拖曳的 mousemove 拿得到「最新寬度」而不必把 width 進相依陣列。
  const widthRef = useRef(width);

  // 寬度變動：記到 localStorage + 同步進 ref（在 effect 裡寫 ref，避免 render 期間動 ref）
  useEffect(() => {
    widthRef.current = width;
    localStorage.setItem(WIDTH_KEY, String(width));
  }, [width]);

  const startResize = useCallback((e) => {
    e.preventDefault();
    const startX = e.clientX;
    const startW = widthRef.current;
    const onMove = (ev) => {
      const next = startW + (startX - ev.clientX);
      setWidth(Math.min(MAX_W, Math.max(MIN_W, next)));
    };
    const onUp = () => {
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
    };
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
  }, []);

  // ----- 資料狀態 -----
  const [presets, setPresets] = useState([]);
  const [runs, setRuns] = useState([]);
  const [favOnly, setFavOnly] = useState(false);
  const [err, setErr] = useState("");

  // 新增方案表單
  const [newPreset, setNewPreset] = useState({
    name: "",
    strategy_key: "ma_crossover",
    symbol: "",
  });

  // 回測：哪個方案正在跑、結果
  const [btRunningId, setBtRunningId] = useState(null);
  const [btResult, setBtResult] = useState(null);

  // Claude 聊天
  const [messages, setMessages] = useState([]);
  const [chatInput, setChatInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);

  // 載入方案 + 回測歷史
  const loadPresets = useCallback(async () => {
    try {
      setPresets(await api.getPresets());
    } catch (e) {
      setErr(e.message);
    }
  }, []);
  const loadRuns = useCallback(async () => {
    try {
      setRuns(await api.getBacktestRuns(favOnly));
    } catch (e) {
      setErr(e.message);
    }
  }, [favOnly]);

  // 掛載 / favOnly 改變時抓資料。loadPresets/loadRuns 都是 async，setState 在 await
  // 之後才跑（非同步），不會造成 cascading render；lint 規則看不穿 async 故誤報，
  // 這裡明確關掉那一行。
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadPresets();
  }, [loadPresets]);
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadRuns();
  }, [loadRuns]);

  // ----- 方案動作 -----
  async function handleCreatePreset() {
    if (!newPreset.name || !newPreset.symbol) {
      setErr("方案名稱與股票代號不能空白");
      return;
    }
    setErr("");
    try {
      await api.createPreset({
        name: newPreset.name,
        strategy_key: newPreset.strategy_key,
        symbol: newPreset.symbol.toUpperCase(),
        params: {},
      });
      setNewPreset({ ...newPreset, name: "", symbol: "" });
      loadPresets();
    } catch (e) {
      setErr(e.message);
    }
  }

  // 改名 + 調參數（用 prompt 做最簡版；日後可換成 Dialog）
  async function handleEditPreset(p) {
    const name = window.prompt("方案名稱：", p.name);
    if (name === null) return;
    const paramsStr = window.prompt(
      "策略參數（JSON，例如 {\"period\": 14}）：",
      JSON.stringify(p.params || {})
    );
    if (paramsStr === null) return;
    let params;
    try {
      params = JSON.parse(paramsStr || "{}");
    } catch {
      setErr("參數不是合法 JSON");
      return;
    }
    try {
      await api.updatePreset(p.id, {
        name,
        strategy_key: p.strategy_key,
        symbol: p.symbol,
        params,
        is_favorite: p.is_favorite,
        notes: p.notes,
      });
      loadPresets();
    } catch (e) {
      setErr(e.message);
    }
  }

  async function toggleFavoritePreset(p) {
    try {
      await api.updatePreset(p.id, { ...p, is_favorite: !p.is_favorite });
      loadPresets();
    } catch (e) {
      setErr(e.message);
    }
  }

  async function handleDeletePreset(p) {
    if (!window.confirm(`確定刪除方案「${p.name}」？（回測歷史會保留）`)) return;
    try {
      await api.deletePreset(p.id);
      loadPresets();
    } catch (e) {
      setErr(e.message);
    }
  }

  // 一鍵回測（Python）
  async function handleBacktest(p) {
    setErr("");
    setBtResult(null);
    setBtRunningId(p.id);
    try {
      const r = await api.backtestPreset(p.id, { days: 365, initial_cash: 10000 });
      setBtResult({ presetName: p.name, ...r });
      loadRuns(); // 歷史多一筆，重抓
    } catch (e) {
      setErr(e.message);
    } finally {
      setBtRunningId(null);
    }
  }

  // 收藏/取消收藏某筆回測
  async function toggleFavoriteRun(run) {
    try {
      await api.favoriteBacktestRun(run.id, !run.is_good);
      loadRuns();
    } catch (e) {
      setErr(e.message);
    }
  }

  // 對某筆回測請 Claude 檢討（結果丟進聊天區顯示）
  async function handlePostmortem(run) {
    setChatLoading(true);
    try {
      const r = await api.postmortem(run.id);
      // 把 AI 參考過的過去探討（檔名）轉成 run#N 顯示在檢討末尾
      const refs = (r.references || []).map((f) => {
        const m = f.match(/run-0*(\d+)-/);
        return m ? `run#${m[1]}` : f;
      });
      const refLine = refs.length ? `\n\n📎 參考過去探討：${refs.join("、")}` : "";
      setMessages((prev) => [
        ...prev,
        { role: "user", content: `請檢討回測 #${run.id}（${run.strategy_key} / ${run.symbol}）` },
        { role: "assistant", content: r.postmortem + refLine },
      ]);
      loadRuns(); // 該筆已標「已檢討」，重抓歷史更新狀態
    } catch (e) {
      setErr(e.message);
    } finally {
      setChatLoading(false);
    }
  }

  // 送聊天訊息
  async function handleSendChat() {
    const text = chatInput.trim();
    if (!text) return;
    const next = [...messages, { role: "user", content: text }];
    setMessages(next);
    setChatInput("");
    setChatLoading(true);
    try {
      const r = await api.sendChat(next);
      setMessages((prev) => [...prev, { role: "assistant", content: r.reply }]);
    } catch (e) {
      setErr(e.message);
    } finally {
      setChatLoading(false);
    }
  }

  // ====== 收合狀態：只顯示細邊條 ======
  if (collapsed) {
    return (
      <Box
        sx={{
          width: 44,
          flexShrink: 0,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          py: 2,
          borderLeft: "1px solid rgba(0,184,212,0.18)",
          background: "linear-gradient(180deg, rgba(0,184,212,0.06), transparent)",
        }}
      >
        <Tooltip title="展開策略工作台" placement="left">
          <IconButton onClick={() => setCollapsed(false)} sx={{ color: NEON.cyan }}>
            ◀
          </IconButton>
        </Tooltip>
        <Typography
          sx={{
            mt: 2,
            writingMode: "vertical-rl",
            fontFamily: '"Sora", sans-serif',
            fontWeight: 700,
            letterSpacing: 2,
            color: NEON.cyan,
          }}
        >
          策略工作台
        </Typography>
      </Box>
    );
  }

  // ====== 展開狀態 ======
  return (
    <Box
      sx={{
        position: "relative",
        width,
        flexShrink: 0,
        display: "flex",
      }}
    >
      {/* 左緣 6px 拖曳把手 */}
      <Box
        onMouseDown={startResize}
        sx={{
          width: 6,
          cursor: "col-resize",
          flexShrink: 0,
          "&:hover": { background: "rgba(0,184,212,0.25)" },
        }}
      />

      <Box
        sx={{
          flex: 1,
          minWidth: 0,
          height: "calc(100vh - 80px)",
          overflowY: "auto",
          p: 2,
          borderLeft: "1px solid rgba(0,184,212,0.18)",
          background: "linear-gradient(180deg, rgba(0,184,212,0.05), transparent)",
        }}
      >
        {/* 標題列 + 收合鈕 */}
        <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 1 }}>
          <Typography variant="h6" sx={{ color: NEON.cyan }}>
            策略工作台
          </Typography>
          <Tooltip title="收合面板">
            <IconButton size="small" onClick={() => setCollapsed(true)}>
              ▶
            </IconButton>
          </Tooltip>
        </Stack>
        <Typography variant="caption" color="text.secondary">
          設計策略 → Python 一鍵回測 → 看期望值 EV 挑最優 → Claude 事後檢討。
        </Typography>

        {err && (
          <Alert severity="error" sx={{ my: 1 }} onClose={() => setErr("")}>
            {err}
          </Alert>
        )}

        {/* ===== 區 1：策略方案 ===== */}
        <SectionTitle>① 策略方案</SectionTitle>
        <Paper variant="outlined" sx={{ p: 1.5, mb: 2 }}>
          <Stack spacing={1}>
            <TextField
              size="small"
              label="方案名稱"
              value={newPreset.name}
              onChange={(e) => setNewPreset({ ...newPreset, name: e.target.value })}
            />
            <Stack direction="row" spacing={1}>
              <TextField
                size="small"
                select
                label="策略"
                sx={{ flex: 1 }}
                value={newPreset.strategy_key}
                onChange={(e) => setNewPreset({ ...newPreset, strategy_key: e.target.value })}
              >
                {STRATEGIES.map((s) => (
                  <MenuItem key={s.value} value={s.value}>
                    {s.label}
                  </MenuItem>
                ))}
              </TextField>
              <TextField
                size="small"
                label="股票"
                sx={{ width: 100 }}
                value={newPreset.symbol}
                onChange={(e) => setNewPreset({ ...newPreset, symbol: e.target.value })}
              />
            </Stack>
            <Button variant="contained" size="small" onClick={handleCreatePreset}>
              ＋ 新增方案
            </Button>
          </Stack>
        </Paper>

        <Stack spacing={1} sx={{ mb: 2 }}>
          {presets.length === 0 && (
            <Typography variant="caption" color="text.secondary">
              還沒有方案，先在上面新增一個。
            </Typography>
          )}
          {presets.map((p) => (
            <Paper key={p.id} variant="outlined" sx={{ p: 1.5 }}>
              <Stack direction="row" alignItems="center" justifyContent="space-between">
                <Box sx={{ minWidth: 0 }}>
                  <Typography variant="subtitle2" noWrap>
                    {p.is_favorite ? "★ " : ""}
                    {p.name}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {strategyLabel(p.strategy_key)} · {p.symbol}
                  </Typography>
                </Box>
                <Stack direction="row" spacing={0.5}>
                  <Tooltip title="收藏">
                    <IconButton size="small" onClick={() => toggleFavoritePreset(p)}>
                      {p.is_favorite ? "★" : "☆"}
                    </IconButton>
                  </Tooltip>
                  <Tooltip title="改名／調參數">
                    <IconButton size="small" onClick={() => handleEditPreset(p)}>
                      ✎
                    </IconButton>
                  </Tooltip>
                  <Tooltip title="刪除">
                    <IconButton size="small" onClick={() => handleDeletePreset(p)}>
                      🗑
                    </IconButton>
                  </Tooltip>
                </Stack>
              </Stack>
              <Button
                size="small"
                variant="outlined"
                fullWidth
                sx={{ mt: 1 }}
                disabled={btRunningId === p.id}
                onClick={() => handleBacktest(p)}
              >
                {btRunningId === p.id ? "回測中…" : "▶ 跑回測（Python）"}
              </Button>
            </Paper>
          ))}
        </Stack>

        {/* ===== 區 2：回測結果卡（EV 當頭條） ===== */}
        {btResult && (
          <>
            <SectionTitle>② 最近一次回測結果</SectionTitle>
            <Paper variant="outlined" sx={{ p: 1.5, mb: 2 }}>
              <Typography variant="caption" color="text.secondary">
                {btResult.presetName}
              </Typography>
              {/* EV 頭條 */}
              <Box sx={{ my: 1, textAlign: "center" }}>
                <Typography variant="caption" color="text.secondary">
                  期望值 EV／筆
                </Typography>
                <Typography
                  variant="h4"
                  sx={{
                    fontFamily: '"Sora", sans-serif',
                    fontWeight: 700,
                    color:
                      btResult.expected_value >= 0 ? NEON.green : NEON.red,
                  }}
                >
                  {btResult.expected_value >= 0 ? "+" : ""}
                  {btResult.expected_value}
                </Typography>
              </Box>
              <Stack direction="row" flexWrap="wrap" gap={0.5} sx={{ mb: 1 }}>
                <Chip size="small" label={`勝率 ${btResult.win_rate_pct}%`} />
                <Chip size="small" label={`PF ${btResult.profit_factor ?? "—"}`} />
                <Chip size="small" label={`總報酬 ${btResult.total_return_pct}%`} />
                <Chip size="small" label={`回撤 ${btResult.max_drawdown_pct}%`} />
                <Chip size="small" label={`買賣 ${btResult.num_round_trips} 筆`} />
                {/* quantstats 風險調整後指標（有算出才顯示） */}
                {btResult.extended?.sharpe != null && (
                  <Chip size="small" label={`Sharpe ${btResult.extended.sharpe}`} />
                )}
                {btResult.extended?.sortino != null && (
                  <Chip size="small" label={`Sortino ${btResult.extended.sortino}`} />
                )}
              </Stack>
              {btResult.run_id && (
                <Button
                  size="small"
                  onClick={() => window.open(api.reportUrl(btResult.run_id), "_blank")}
                >
                  📊 開啟完整績效報表
                </Button>
              )}
              {btResult.expected_value < 0 && (
                <Alert severity="warning" sx={{ mt: 1 }}>
                  EV 為負（長期不賺）。建議到下方歷史按「檢討」請 Claude 分析錯在哪。
                </Alert>
              )}
            </Paper>
          </>
        )}

        {/* ===== 區 3：回測歷史 / 好策略榜 ===== */}
        <Stack direction="row" alignItems="center" justifyContent="space-between">
          <SectionTitle>③ 回測歷史（依 EV 排序）</SectionTitle>
          <Button size="small" onClick={() => setFavOnly((v) => !v)}>
            {favOnly ? "顯示全部" : "只看好策略 ★"}
          </Button>
        </Stack>
        <Stack spacing={1} sx={{ mb: 2 }}>
          {runs.length === 0 && (
            <Typography variant="caption" color="text.secondary">
              還沒有回測紀錄。
            </Typography>
          )}
          {runs.map((run) => (
            <Paper key={run.id} variant="outlined" sx={{ p: 1.5 }}>
              <Stack direction="row" alignItems="center" justifyContent="space-between">
                <Box sx={{ minWidth: 0 }}>
                  <Typography variant="subtitle2" noWrap>
                    <span
                      style={{
                        color:
                          (run.expected_value ?? 0) >= 0 ? NEON.green : NEON.red,
                        fontWeight: 700,
                      }}
                    >
                      EV {run.expected_value ?? "—"}
                    </span>
                    {"  "}
                    <Typography component="span" variant="caption" color="text.secondary">
                      {strategyLabel(run.strategy_key)} · {run.symbol}
                    </Typography>
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    勝率 {run.win_rate_pct}% · 報酬 {run.total_return_pct}% ·{" "}
                    {run.has_postmortem ? "已檢討" : "未檢討"}
                  </Typography>
                </Box>
                <Stack direction="row" spacing={0.5}>
                  <Tooltip title="收藏為好策略">
                    <IconButton size="small" onClick={() => toggleFavoriteRun(run)}>
                      {run.is_good ? "★" : "☆"}
                    </IconButton>
                  </Tooltip>
                  <Tooltip title="開啟績效報表">
                    <IconButton
                      size="small"
                      onClick={() => window.open(api.reportUrl(run.id), "_blank")}
                    >
                      📊
                    </IconButton>
                  </Tooltip>
                  <Tooltip title="總結這次錯在哪">
                    <IconButton size="small" onClick={() => handlePostmortem(run)}>
                      💬
                    </IconButton>
                  </Tooltip>
                </Stack>
              </Stack>
            </Paper>
          ))}
        </Stack>

        {/* ===== 區 4：Claude 助手 ===== */}
        <SectionTitle>④ Claude 助手</SectionTitle>
        <Paper variant="outlined" sx={{ p: 1.5 }}>
          <Box
            sx={{
              maxHeight: 240,
              overflowY: "auto",
              mb: 1,
              display: "flex",
              flexDirection: "column",
              gap: 0.5,
            }}
          >
            {messages.length === 0 && (
              <Typography variant="caption" color="text.secondary">
                問助手制定策略、調參建議，或在上方按「檢討」做事後分析。
                （需在後端啟動本機 Ollama，或在 .env 改接其他免費供應商。）
              </Typography>
            )}
            {messages.map((m, i) => (
              <Box
                key={i}
                sx={{
                  alignSelf: m.role === "user" ? "flex-end" : "flex-start",
                  maxWidth: "85%",
                  px: 1.2,
                  py: 0.8,
                  borderRadius: 2,
                  whiteSpace: "pre-wrap",
                  fontSize: 13,
                  background:
                    m.role === "user"
                      ? "rgba(0,184,212,0.12)"
                      : "rgba(26,34,56,0.05)",
                }}
              >
                {m.content}
              </Box>
            ))}
            {chatLoading && <CircularProgress size={18} sx={{ alignSelf: "center" }} />}
          </Box>
          <Stack direction="row" spacing={1}>
            <TextField
              size="small"
              fullWidth
              placeholder="輸入訊息…"
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleSendChat();
                }
              }}
            />
            <Button variant="contained" size="small" onClick={handleSendChat} disabled={chatLoading}>
              送出
            </Button>
          </Stack>
        </Paper>
      </Box>
    </Box>
  );
}

// 小標題（區塊分隔）
function SectionTitle({ children }) {
  return (
    <Typography
      variant="subtitle2"
      sx={{
        mt: 2,
        mb: 1,
        fontFamily: '"Sora", sans-serif',
        fontWeight: 700,
        color: "text.primary",
      }}
    >
      {children}
    </Typography>
  );
}
