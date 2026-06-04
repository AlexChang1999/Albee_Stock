// ============================================================
// AiRecommendations：AI 策略探勘中心（Phase 2）
// ============================================================
// 按一下「開始掃描」→ 後端跑漏斗式海選（量能篩選 → 多策略回測取 EV 最高）→
// 把高期望值（EV>0）的策略配置渲染成卡片。每張卡片可「一鍵部署」成 Bot。
//
// 資料來源：後端 GET /ai-recommendations（底層 services/screener.py，預設用免費 yfinance）。
// 設計：本元件自管「掃描狀態與結果」；真正建立 Bot 的動作交給父層 onDeploy 處理，
//       這樣建立後的訊息提示與 Bot 列表重新整理都統一在 App 那邊。

import { useState } from "react";
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  Alert,
  Chip,
  Grid,
  TextField,
  CircularProgress,
  Divider,
} from "@mui/material";
import { api } from "../api";
import { STRATEGIES } from "../constants";

// 策略代號 → 中文名稱（查不到就原樣顯示）
function strategyLabel(key) {
  return STRATEGIES.find((s) => s.value === key)?.label || key;
}

// 把數字漂亮顯示；null/undefined 顯示「—」
function fmt(v, suffix = "") {
  if (v === null || v === undefined) return "—";
  return `${v}${suffix}`;
}

// 一個指標的小區塊（label 在上、value 在下）
function Metric({ label, value, highlight }) {
  return (
    <Box sx={{ textAlign: "center", flex: 1 }}>
      <Typography variant="caption" color="text.secondary" display="block">
        {label}
      </Typography>
      <Typography
        variant="body2"
        sx={{ fontWeight: highlight ? 700 : 500, color: highlight ? "primary.main" : "text.primary" }}
      >
        {value}
      </Typography>
    </Box>
  );
}

// 單張推薦卡片
function RecommendationCard({ rec, onDeploy, deploying }) {
  const m = rec.metrics || {};
  const ret = m.total_return_pct;
  // 報酬率正綠負紅
  const retColor =
    ret == null ? "text.primary" : ret >= 0 ? "success.main" : "error.main";

  return (
    <Card variant="outlined" sx={{ height: "100%" }}>
      <CardContent>
        {/* 標題列：股票代號 + 量比徽章 */}
        <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 0.5 }}>
          <Typography variant="h6" sx={{ fontWeight: 700 }}>
            {rec.symbol}
          </Typography>
          <Chip
            size="small"
            color="warning"
            label={`量比 ${fmt(rec.volume_ratio, "x")}`}
          />
        </Box>

        {/* 推薦策略 */}
        <Typography variant="body2" color="text.secondary" gutterBottom>
          推薦策略：<strong>{strategyLabel(rec.strategy_key)}</strong>
        </Typography>

        <Divider sx={{ my: 1 }} />

        {/* 關鍵指標：EV 當頭條 */}
        <Box sx={{ display: "flex", mb: 1 }}>
          <Metric label="期望值 EV" value={fmt(m.expected_value)} highlight />
          <Metric label="勝率" value={fmt(m.win_rate_pct, "%")} />
          <Metric
            label="總報酬"
            value={
              <Box component="span" sx={{ color: retColor }}>
                {fmt(ret, "%")}
              </Box>
            }
          />
        </Box>
        <Box sx={{ display: "flex", mb: 1.5 }}>
          <Metric label="最大回撤" value={fmt(m.max_drawdown_pct, "%")} />
          <Metric label="獲利因子" value={fmt(m.profit_factor)} />
          <Metric label="交易筆數" value={fmt(m.num_round_trips)} />
        </Box>

        {/* 一鍵部署：建立 Bot 並掛上排程 */}
        <Button
          fullWidth
          variant="contained"
          disabled={deploying}
          onClick={() => onDeploy(rec)}
        >
          {deploying ? "部署中…" : "🚀 一鍵部署"}
        </Button>
      </CardContent>
    </Card>
  );
}

export default function AiRecommendations({ onDeploy }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [data, setData] = useState(null); // 後端回的完整結果（含 recommendations 等）
  const [deployingKey, setDeployingKey] = useState(""); // 正在部署哪一張（symbol+strategy）
  // 海選參數（給進階使用者調；新手用預設即可）
  const [volMult, setVolMult] = useState(2.5);
  const [minEv, setMinEv] = useState(0);

  // 觸發一次海選
  async function handleScan() {
    setLoading(true);
    setError("");
    setData(null);
    try {
      const r = await api.getAiRecommendations({
        volume_multiplier: volMult,
        min_ev: minEv,
        source: "yfinance",
      });
      setData(r);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  // 包一層：部署時鎖住該張卡的按鈕，完成後解鎖
  async function deploy(rec) {
    const key = `${rec.symbol}-${rec.strategy_key}`;
    setDeployingKey(key);
    try {
      await onDeploy(rec);
    } finally {
      setDeployingKey("");
    }
  }

  const recs = data?.recommendations || [];

  return (
    <Box>
      {/* 說明 + 掃描控制列 */}
      <Card variant="outlined" sx={{ mb: 2 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            AI 策略探勘中心
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            漏斗式海選：先用「量能（量比）」篩出值得注意的標的，再對它們跑多種策略回測，
            挑出期望值（EV）最高的配置推薦給你。檢閱後可一鍵部署成 Bot。
          </Typography>

          <Box sx={{ display: "flex", gap: 2, alignItems: "center", flexWrap: "wrap" }}>
            <TextField
              size="small"
              type="number"
              label="量比門檻"
              helperText="最新量 / 20日均量 ≥"
              value={volMult}
              onChange={(e) => setVolMult(e.target.value)}
              sx={{ width: 140 }}
            />
            <TextField
              size="small"
              type="number"
              label="EV 門檻"
              helperText="期望值 ≥"
              value={minEv}
              onChange={(e) => setMinEv(e.target.value)}
              sx={{ width: 140 }}
            />
            <Button variant="contained" onClick={handleScan} disabled={loading}>
              {loading ? "掃描中…" : "開始掃描"}
            </Button>
          </Box>
        </CardContent>
      </Card>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {/* 掃描中：轉圈提示（海選可能要幾秒到幾十秒）*/}
      {loading && (
        <Box sx={{ display: "flex", alignItems: "center", gap: 2, py: 4, justifyContent: "center" }}>
          <CircularProgress size={24} />
          <Typography color="text.secondary">
            海選中…正在量能篩選並跑回測，請稍候
          </Typography>
        </Box>
      )}

      {/* 掃描完成的摘要 */}
      {data && !loading && (
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          掃描池 {data.universe_size} 檔 → 量能過關 {data.layer1_passed?.length ?? 0} 檔 →
          推薦 {recs.length} 筆（依 EV 由高到低）
        </Typography>
      )}

      {/* 推薦卡片網格 */}
      {!loading && recs.length > 0 && (
        <Grid container spacing={2}>
          {recs.map((rec) => (
            <Grid item xs={12} sm={6} md={4} key={`${rec.symbol}-${rec.strategy_key}`}>
              <RecommendationCard
                rec={rec}
                onDeploy={deploy}
                deploying={deployingKey === `${rec.symbol}-${rec.strategy_key}`}
              />
            </Grid>
          ))}
        </Grid>
      )}

      {/* 掃完但沒有任何推薦 */}
      {data && !loading && recs.length === 0 && (
        <Alert severity="info">
          這輪沒有符合條件的推薦。可調低「量比門檻」或「EV 門檻」後再掃一次。
        </Alert>
      )}
    </Box>
  );
}
