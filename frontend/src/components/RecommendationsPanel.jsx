// ============================================================
// RecommendationsPanel：AI 策略探勘中心（模式 A 海選）
// ============================================================
// 後端用漏斗式篩選（量能 → 本機 LLM 情緒 → EV 海選）挑出值得部署的策略，
// 這裡把回傳結果渲染成一張張卡片：每張顯示標的、最佳策略、期望值 EV（頭條）、
// 勝率/回撤、情緒燈號，最後一顆「一鍵部署」按鈕。
//
// 設計：海選是「重」運算（要抓資料、跑回測、可能呼叫 LLM），所以**不自動跑**，
// 由使用者按「開始掃描」才打 API；按「重新掃描」可忽略後端快取強制重算。
//
// props:
//   onDeploy(rec)：父層提供的部署函式（建立 Bot + 掛排程，走既有 /bots 流程）

import { useState } from "react";
import {
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Typography,
  CircularProgress,
  Alert,
} from "@mui/material";

import { api } from "../api";

// 情緒分數 → 顯示用的顏色與標籤（None = 沒跑情緒分析）
function sentimentChip(sentiment) {
  if (!sentiment) return { label: "情緒未分析", color: "default" };
  const { label, score } = sentiment;
  if (label === "bullish") return { label: `偏多 ${score}`, color: "success" };
  if (label === "bearish") return { label: `偏空 ${score}`, color: "error" };
  return { label: `中性 ${score}`, color: "default" };
}

export default function RecommendationsPanel({ onDeploy }) {
  const [data, setData] = useState(null); // 後端回傳的整包結果
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [deployingId, setDeployingId] = useState(null); // 正在部署哪一檔（避免連點）

  async function scan(refresh = false) {
    setLoading(true);
    setError("");
    try {
      const res = await api.getRecommendations({ refresh });
      setData(res);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleDeploy(rec) {
    setDeployingId(rec.symbol);
    try {
      await onDeploy(rec);
    } finally {
      setDeployingId(null);
    }
  }

  const recs = data?.recommendations || [];

  return (
    <Box>
      {/* 控制列 */}
      <Box sx={{ display: "flex", gap: 1, alignItems: "center", mb: 2 }}>
        <Button variant="contained" onClick={() => scan(false)} disabled={loading}>
          {loading ? "掃描中…" : "開始掃描"}
        </Button>
        <Button variant="outlined" onClick={() => scan(true)} disabled={loading}>
          重新掃描（忽略快取）
        </Button>
        {loading && <CircularProgress size={20} />}
      </Box>

      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        漏斗式海選：先用成交量粗篩一籃股票，再對少數爆量標的做情緒分析與 EV 回測，
        最後只列出期望值（EV）為正、值得部署的策略。本機運算，按下才跑。
      </Typography>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      {/* 漏斗統計 */}
      {data && (
        <Typography variant="caption" color="text.secondary">
          候選 {data.watchlist_size} 檔 → 爆量入選 {data.volume_passed} 檔 →
          推薦 {data.recommended} 檔{data.cached ? "（來自快取）" : ""}
        </Typography>
      )}

      {/* 推薦卡片 */}
      <Box
        sx={{
          display: "grid",
          gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr", md: "1fr 1fr 1fr" },
          gap: 2,
          mt: 2,
        }}
      >
        {recs.map((rec) => {
          const m = rec.metrics || {};
          const chip = sentimentChip(rec.sentiment);
          return (
            <Card key={rec.symbol} variant="outlined">
              <CardContent>
                <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <Typography variant="h6">{rec.symbol}</Typography>
                  <Chip size="small" label={chip.label} color={chip.color} />
                </Box>
                <Typography variant="body2" color="text.secondary">
                  最佳策略：{rec.strategy_key}
                </Typography>

                {/* EV 當頭條（大字） */}
                <Typography variant="h4" sx={{ my: 1 }}>
                  EV {Number(m.expected_value).toFixed(2)}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  勝率 {m.win_rate_pct ?? "-"}%｜報酬 {m.total_return_pct ?? "-"}%｜
                  回撤 {m.max_drawdown_pct ?? "-"}%｜量比 {rec.volume_ratio}
                </Typography>

                <Button
                  variant="contained"
                  fullWidth
                  sx={{ mt: 2 }}
                  disabled={deployingId === rec.symbol}
                  onClick={() => handleDeploy(rec)}
                >
                  {deployingId === rec.symbol ? "部署中…" : "一鍵部署"}
                </Button>
              </CardContent>
            </Card>
          );
        })}
      </Box>

      {data && recs.length === 0 && !loading && (
        <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
          這次沒有 EV 為正的推薦。可換時間範圍或稍後再掃。
        </Typography>
      )}
    </Box>
  );
}
