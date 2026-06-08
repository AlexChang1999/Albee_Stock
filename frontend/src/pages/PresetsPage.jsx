// ============================================================
// PresetsPage：策略方案頁（/presets）
// ============================================================
// Phase 9 step-04：把右側工作台的策略方案搬成獨立全頁：
//   CRUD（新增 / 改名 / 調參 / 收藏 / 刪除）+ 一鍵跑回測。
// 沿用工作台既有的方案邏輯與 api，不自造新表單風格；刪除用既有 ConfirmDialog。

import { useState, useEffect, useCallback } from "react";
import {
  Box,
  Typography,
  TextField,
  MenuItem,
  Button,
  Paper,
  IconButton,
  Stack,
  Tooltip,
  Alert,
  Grid,
} from "@mui/material";
import { api } from "../api";
import { STRATEGIES } from "../constants";
import ConfirmDialog from "../components/ConfirmDialog";
import BacktestResultCard from "../components/BacktestResultCard";

function strategyLabel(key) {
  return STRATEGIES.find((s) => s.value === key)?.label || key;
}

export default function PresetsPage() {
  const [presets, setPresets] = useState([]);
  const [err, setErr] = useState("");
  const [newPreset, setNewPreset] = useState({
    name: "",
    strategy_key: "ma_crossover",
    symbol: "",
  });
  const [btRunningId, setBtRunningId] = useState(null);
  const [btResult, setBtResult] = useState(null);
  const [deleteTarget, setDeleteTarget] = useState(null);

  const loadPresets = useCallback(async () => {
    try {
      setPresets(await api.getPresets());
    } catch (e) {
      setErr(e.message);
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadPresets();
  }, [loadPresets]);

  async function handleCreate() {
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

  // 改名 + 調參數（沿用工作台的 prompt 既有做法）
  async function handleEdit(p) {
    const name = window.prompt("方案名稱：", p.name);
    if (name === null) return;
    const paramsStr = window.prompt(
      '策略參數（JSON，例如 {"period": 14}）：',
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

  async function toggleFavorite(p) {
    try {
      await api.updatePreset(p.id, { ...p, is_favorite: !p.is_favorite });
      loadPresets();
    } catch (e) {
      setErr(e.message);
    }
  }

  async function confirmDelete() {
    const p = deleteTarget;
    setDeleteTarget(null);
    try {
      await api.deletePreset(p.id);
      loadPresets();
    } catch (e) {
      setErr(e.message);
    }
  }

  async function handleBacktest(p) {
    setErr("");
    setBtResult(null);
    setBtRunningId(p.id);
    try {
      const r = await api.backtestPreset(p.id, { days: 365, initial_cash: 10000 });
      setBtResult({ presetName: p.name, ...r });
    } catch (e) {
      setErr(e.message);
    } finally {
      setBtRunningId(null);
    }
  }

  return (
    <Box>
      <Typography variant="h4" sx={{ mb: 2 }}>
        策略方案
      </Typography>

      {err && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setErr("")}>
          {err}
        </Alert>
      )}

      {/* 新增方案 */}
      <Paper variant="outlined" sx={{ p: 2, mb: 3 }}>
        <Stack direction={{ xs: "column", sm: "row" }} spacing={1} alignItems="center">
          <TextField
            size="small"
            label="方案名稱"
            value={newPreset.name}
            onChange={(e) => setNewPreset({ ...newPreset, name: e.target.value })}
          />
          <TextField
            size="small"
            select
            label="策略"
            sx={{ minWidth: 160 }}
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
            sx={{ width: 120 }}
            value={newPreset.symbol}
            onChange={(e) => setNewPreset({ ...newPreset, symbol: e.target.value })}
          />
          <Button variant="contained" onClick={handleCreate}>
            ＋ 新增方案
          </Button>
        </Stack>
      </Paper>

      {/* 方案清單 */}
      <Grid container spacing={2} sx={{ mb: 3 }}>
        {presets.length === 0 && (
          <Grid item xs={12}>
            <Typography variant="caption" color="text.secondary">
              還沒有方案，先在上面新增一個。
            </Typography>
          </Grid>
        )}
        {presets.map((p) => (
          <Grid item xs={12} sm={6} md={4} key={p.id}>
            <Paper variant="outlined" sx={{ p: 1.5 }}>
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
                    <IconButton size="small" onClick={() => toggleFavorite(p)}>
                      {p.is_favorite ? "★" : "☆"}
                    </IconButton>
                  </Tooltip>
                  <Tooltip title="改名／調參數">
                    <IconButton size="small" onClick={() => handleEdit(p)}>
                      ✎
                    </IconButton>
                  </Tooltip>
                  <Tooltip title="刪除">
                    <IconButton size="small" onClick={() => setDeleteTarget(p)}>
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
          </Grid>
        ))}
      </Grid>

      {/* 最近一次回測結果 */}
      {btResult && (
        <Box sx={{ maxWidth: 420 }}>
          <Typography variant="h6" sx={{ mb: 1 }}>
            最近一次回測
          </Typography>
          <BacktestResultCard
            metrics={btResult}
            title={btResult.presetName}
            runId={btResult.run_id}
          />
        </Box>
      )}

      <ConfirmDialog
        open={!!deleteTarget}
        title="刪除策略方案"
        message={
          deleteTarget
            ? `確定刪除方案「${deleteTarget.name}」？（回測歷史會保留）`
            : ""
        }
        confirmText="刪除"
        onConfirm={confirmDelete}
        onClose={() => setDeleteTarget(null)}
      />
    </Box>
  );
}
