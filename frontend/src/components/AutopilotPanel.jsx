// ============================================================
// AutopilotPanel：模式 B 自動駕駛控制台（Phase 4）
// ============================================================
// 顯示後端「全局自動化規則」（EV/勝率門檻、頻率、上限、下單環境），
// 並提供兩個動作：
//   1. 開/關 週期掃描（toggle，不改 .env，只動記憶體排程）
//   2. 立刻手動掃描一次（scan-now，force=true，達標就實際部署 Bot）
//
// 安全提醒：模式 B 達標會「無需人工確認」自動建立 Bot。真正下單仍受實盤雙閘
//          安全閥保護——沒開實盤就只在 Paper 模擬，不燒真錢。面板會明確標示環境。
//
// 資料來源：GET /automation/rules、POST /automation/toggle、POST /automation/scan-now。
// 部署後呼叫父層 onReload() 讓 Bot 列表刷新。

import { useState, useEffect } from "react";
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  Switch,
  FormControlLabel,
  Alert,
  Chip,
  Stack,
  CircularProgress,
} from "@mui/material";
import { api } from "../api";

// 規則的單一欄位顯示（label 上、value 下）
function RuleItem({ label, value }) {
  return (
    <Box>
      <Typography variant="caption" color="text.secondary" display="block">
        {label}
      </Typography>
      <Typography variant="body2" sx={{ fontWeight: 600 }}>
        {value}
      </Typography>
    </Box>
  );
}

export default function AutopilotPanel({ onReload }) {
  const [rules, setRules] = useState(null);
  const [loading, setLoading] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null); // 最近一次手動掃描的摘要

  // 載入目前規則
  async function loadRules() {
    setError("");
    try {
      const r = await api.getAutomationRules();
      setRules(r);
    } catch (e) {
      setError(e.message);
    }
  }

  useEffect(() => {
    loadRules();
  }, []);

  // 開/關週期掃描
  async function handleToggle(enable) {
    setLoading(true);
    setError("");
    try {
      await api.toggleAutomation(enable);
      await loadRules();
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  // 立刻手動掃描一次
  async function handleScanNow() {
    setScanning(true);
    setError("");
    setResult(null);
    try {
      const r = await api.automationScanNow();
      setResult(r);
      // 有部署到新 Bot → 通知父層刷新列表
      if (r.deployed?.length && onReload) onReload();
    } catch (e) {
      setError(e.message);
    } finally {
      setScanning(false);
    }
  }

  if (!rules) {
    return (
      <Card variant="outlined" sx={{ mb: 2 }}>
        <CardContent>
          {error ? (
            <Alert severity="error">{error}</Alert>
          ) : (
            <Typography color="text.secondary">載入自動駕駛規則中…</Typography>
          )}
        </CardContent>
      </Card>
    );
  }

  return (
    <Card variant="outlined" sx={{ mb: 2 }}>
      <CardContent>
        {/* 標題列 + 環境徽章 */}
        <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 1, flexWrap: "wrap" }}>
          <Typography variant="h6">🤖 模式 B：自動駕駛</Typography>
          <Chip
            size="small"
            color={rules.live_armed ? "error" : "success"}
            label={rules.live_armed ? "⚠️ 實盤（真錢）" : "模擬 Paper"}
          />
          {/* 週期掃描是否正在跑 */}
          <Chip
            size="small"
            variant="outlined"
            color={rules.running ? "primary" : "default"}
            label={rules.running ? "週期掃描：運行中" : "週期掃描：停止"}
            sx={{ ml: "auto" }}
          />
        </Box>

        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          系統會週期性自動海選，當策略 <strong>EV ≥ {rules.min_ev}</strong> 且{" "}
          <strong>勝率 ≥ {rules.min_win_rate}%</strong> 時，<strong>無需人工確認</strong>
          自動建立 Bot 並掛排程（上限 {rules.max_bots} 個）。下單仍受實盤雙閘保護。
        </Typography>

        {/* 規則一覽 */}
        <Stack
          direction="row"
          spacing={3}
          sx={{ flexWrap: "wrap", gap: 2, mb: 2 }}
        >
          <RuleItem label="EV 門檻" value={rules.min_ev} />
          <RuleItem label="勝率門檻" value={`${rules.min_win_rate}%`} />
          <RuleItem label="掃描頻率" value={`${rules.interval_sec}s`} />
          <RuleItem label="Bot 上限" value={rules.max_bots} />
          <RuleItem label="單筆金額" value={`$${rules.trade_amount}`} />
          <RuleItem
            label=".env 總開關"
            value={rules.enabled ? "已開啟" : "關閉（預設）"}
          />
        </Stack>

        {/* 操作列 */}
        <Box sx={{ display: "flex", gap: 2, alignItems: "center", flexWrap: "wrap" }}>
          <FormControlLabel
            control={
              <Switch
                checked={rules.running}
                disabled={loading}
                onChange={(e) => handleToggle(e.target.checked)}
              />
            }
            label="週期自動掃描"
          />
          <Button
            variant="outlined"
            onClick={handleScanNow}
            disabled={scanning}
            startIcon={scanning ? <CircularProgress size={16} /> : null}
          >
            {scanning ? "掃描中…" : "立刻掃描一次"}
          </Button>
        </Box>

        {error && (
          <Alert severity="error" sx={{ mt: 2 }}>
            {error}
          </Alert>
        )}

        {/* 手動掃描結果摘要 */}
        {result && (
          <Alert
            severity={result.deployed?.length ? "success" : "info"}
            sx={{ mt: 2 }}
          >
            {result.ran === false ? (
              <>未執行：{result.reason}</>
            ) : (
              <>
                掃描完成：候選 {result.candidates ?? 0} 筆，
                自動部署 <strong>{result.deployed?.length ?? 0}</strong> 個 Bot
                {result.rejected_low_win_rate?.length
                  ? `，勝率不足擋下 ${result.rejected_low_win_rate.length} 筆`
                  : ""}
                {result.skipped_existing?.length
                  ? `，已存在跳過 ${result.skipped_existing.length} 檔`
                  : ""}
                {result.cap_reached ? "，已達 Bot 上限" : ""}。
              </>
            )}
          </Alert>
        )}
      </CardContent>
    </Card>
  );
}
