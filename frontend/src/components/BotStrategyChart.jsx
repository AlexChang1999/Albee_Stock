// ============================================================
// BotStrategyChart：策略視角圖表（Stage 4 策略可視化）
// ============================================================
// 選一個 Bot → 在 K 線圖上看到「策略眼中的世界」：
//   - 主圖疊指標線（均線交叉雙線、布林三軌、唐奇安通道…）
//   - 振盪器副圖（RSI/KD/%R/MACD/ADX，含超買超賣參考線）
//   - 真實成交點 ▲▼（TradeLog）+ 可開關的決策觀望點（DecisionLog）
// 一眼看出策略「看什麼、在哪裡出手、為何沒出手」。
//
// 資料全部來自 GET /bots/{id}/chart-data：candles 與指標用同一份 df 算，
// 時間軸保證對齊；顏色後端只回色名，這裡對 NEON 色票映射（深底主題規則）。

import { useEffect, useMemo, useState } from "react";
import {
  Box,
  Card,
  CardContent,
  FormControlLabel,
  MenuItem,
  Switch,
  TextField,
  Typography,
} from "@mui/material";
import LightweightChart from "../LightweightChart";
import { api } from "../api";
import { NEON } from "../theme";

// 後端色名 → NEON 色票（後端不寫死 hex，前端統一吃主題）
const COLOR_MAP = {
  cyan: NEON.cyan,
  gold: NEON.magenta,
  green: NEON.green,
  red: NEON.red,
};

/** 把後端 markers 轉成 lightweight-charts v5 的 marker 格式（依時間排序）。 */
function toChartMarkers(markers, showDecisions) {
  return (markers || [])
    .filter((m) => m.kind === "trade" || showDecisions)
    .map((m) =>
      m.kind === "trade"
        ? {
            time: m.time,
            position: m.side === "buy" ? "belowBar" : "aboveBar",
            shape: m.side === "buy" ? "arrowUp" : "arrowDown",
            color: m.side === "buy" ? NEON.green : NEON.red,
            text: m.text || "",
          }
        : {
            time: m.time,
            position: "belowBar",
            shape: "circle",
            color: NEON.cyan,
            size: 0.6, // 觀望點縮小，別搶過成交箭頭
            text: "",
          }
    )
    .sort((a, b) => (a.time < b.time ? -1 : a.time > b.time ? 1 : 0));
}

/** 疊線/副圖的色名換成 NEON hex。 */
function resolveColors(lines) {
  return (lines || []).map((ln) => ({
    ...ln,
    color: COLOR_MAP[ln.color] || NEON.cyan,
  }));
}

export default function BotStrategyChart({ bots = [] }) {
  const [botId, setBotId] = useState("");
  const [data, setData] = useState(null);
  const [showDecisions, setShowDecisions] = useState(false);
  const [err, setErr] = useState("");

  // 換 Bot 就重抓圖資料
  useEffect(() => {
    if (botId === "") {
      setData(null);
      return;
    }
    let mounted = true;
    setErr("");
    api
      .getBotChartData(botId)
      .then((res) => mounted && setData(res))
      .catch((e) => mounted && setErr(e.message));
    return () => {
      mounted = false;
    };
  }, [botId]);

  const overlays = useMemo(() => resolveColors(data?.overlays), [data]);
  const pane = useMemo(
    () =>
      data?.pane
        ? { ...data.pane, series: resolveColors(data.pane.series) }
        : null,
    [data]
  );
  const markers = useMemo(
    () => toChartMarkers(data?.markers, showDecisions),
    [data, showDecisions]
  );

  const hasIndicator = overlays.length > 0 || !!pane;

  return (
    <Card sx={{ mb: 3 }}>
      <CardContent>
        <Box sx={{ display: "flex", alignItems: "center", gap: 2, flexWrap: "wrap", mb: 1 }}>
          <Typography variant="h6">策略視角</Typography>
          <TextField
            select
            size="small"
            label="選擇 Bot"
            value={botId}
            onChange={(e) => setBotId(e.target.value)}
            sx={{ minWidth: 200 }}
          >
            <MenuItem value="">— 請選擇 —</MenuItem>
            {bots.map((b) => (
              <MenuItem key={b.id} value={b.id}>
                {b.name}（{b.symbol}）
              </MenuItem>
            ))}
          </TextField>
          <FormControlLabel
            control={
              <Switch
                size="small"
                checked={showDecisions}
                onChange={(e) => setShowDecisions(e.target.checked)}
              />
            }
            label={<Typography variant="caption">顯示觀望點</Typography>}
          />
        </Box>

        {err && (
          <Typography variant="caption" color="error">
            {err}
          </Typography>
        )}

        {botId === "" ? (
          <Typography variant="caption" color="text.secondary">
            選一個 Bot，看它的策略在 K 線上「看什麼、在哪裡出手」——
            指標線、買賣 ▲▼ 標記、觀望點全都來自真實紀錄。
          </Typography>
        ) : (
          data && (
            <>
              {!hasIndicator && (
                <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 0.5 }}>
                  此策略（{data.strategy}）不支援指標疊圖，仍可看成交標記。
                </Typography>
              )}
              <LightweightChart
                symbol={data.symbol}
                height={pane ? 480 : 380}
                candles={data.candles}
                markers={markers}
                overlays={overlays}
                pane={pane}
              />
            </>
          )
        )}
      </CardContent>
    </Card>
  );
}
