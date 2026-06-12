// ============================================================
// PromotionPage：董事會核准（/promotions）
// ============================================================
// Phase 10 step-06：老闆一頁核准 Bot 從 Paper（模擬）晉升到真錢的「人在迴路」關卡。
//   候選（Paper）→ 提議 → 待核 → 核准 / 退回。
//
// ★安全紅線：這裡的「核准」只是多一道人工閘，approved_live 只是「人已同意」旗標，
//   不放行真錢。真錢仍須 ALPACA_BASE_URL 實盤 + ALLOW_LIVE_TRADING=true 雙閘把關。
//   前端不做自動晉升、不重算績效——只顯示後端數字、由使用者點按。
//
// 設計：沿用 EvolutionPage 的「tab 切換 + 卡片 + 動作鈕」與深藍主題（吃 theme/NEON，不寫死 hex）。

import { useState, useEffect, useCallback } from "react";
import {
  Box,
  Typography,
  ToggleButton,
  ToggleButtonGroup,
  Grid,
  Stack,
  Button,
  Alert,
  Card,
  CardContent,
  Chip,
} from "@mui/material";
import { api } from "../api";
import { NEON } from "../theme";

// 狀態 → 顯示文字 / 色票（吃 NEON，不寫死淺色 hex）
const STATUS_META = {
  paper: { label: "候選（Paper）", color: NEON.cyan },
  proposed_live: { label: "待核", color: NEON.magenta }, // 黃金：待老闆強調處理
  approved_live: { label: "已核准", color: NEON.green },
  rejected: { label: "已退回", color: NEON.red },
};

function fmt(v, suffix = "") {
  return v === null || v === undefined ? "—" : `${v}${suffix}`;
}

export default function PromotionPage() {
  const [status, setStatus] = useState("paper");
  const [items, setItems] = useState([]);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [busyId, setBusyId] = useState(null);

  const load = useCallback(async () => {
    setErr("");
    try {
      setItems(await api.getPromotions(status));
    } catch (e) {
      setErr(e.message);
    }
  }, [status]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load();
  }, [load]);

  // 共用動作包裝：跑 API → 顯示訊息 → 重抓清單（出錯顯示後端理由，如未達標 409）
  async function act(botId, fn, okMsg) {
    setErr("");
    setMsg("");
    setBusyId(botId);
    try {
      await fn();
      setMsg(okMsg);
      load();
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusyId(null);
    }
  }

  function propose(it) {
    act(it.bot_id, () => api.proposePromotion(it.bot_id), `已提議 Bot #${it.bot_id} 送董事會核准`);
  }
  function approve(it) {
    act(it.bot_id, () => api.approvePromotion(it.bot_id), `已核准 Bot #${it.bot_id}（仍受實盤雙閘把關）`);
  }
  function reject(it) {
    const reason = window.prompt("退回理由（會記進晉升軌跡）：", "");
    if (reason === null) return;
    act(it.bot_id, () => api.rejectPromotion(it.bot_id, reason), `已退回 Bot #${it.bot_id}`);
  }

  return (
    <Box>
      <Typography variant="h4" sx={{ mb: 1 }}>
        董事會核准
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        核准只是「多一道人工閘」。真錢仍須實盤雙閘（ALPACA_BASE_URL 實盤 + ALLOW_LIVE_TRADING）
        同時打開才會送單——本頁不碰那道安全閥。
      </Typography>

      <ToggleButtonGroup
        size="small"
        exclusive
        value={status}
        onChange={(e, v) => v && setStatus(v)}
        sx={{ mb: 2 }}
      >
        <ToggleButton value="paper">候選（Paper）</ToggleButton>
        <ToggleButton value="proposed_live">待核</ToggleButton>
        <ToggleButton value="approved_live">已核准</ToggleButton>
        <ToggleButton value="rejected">已退回</ToggleButton>
      </ToggleButtonGroup>

      {err && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setErr("")}>
          {err}
        </Alert>
      )}
      {msg && (
        <Alert severity="success" sx={{ mb: 2 }} onClose={() => setMsg("")}>
          {msg}
        </Alert>
      )}

      <Grid container spacing={2}>
        {items.length === 0 && (
          <Grid item xs={12}>
            <Typography variant="caption" color="text.secondary">
              這一層沒有 Bot。
            </Typography>
          </Grid>
        )}
        {items.map((it) => {
          const meta = STATUS_META[it.promotion_status] || {};
          const stats = it.paper_stats || {};
          return (
            <Grid item xs={12} sm={6} md={4} key={it.bot_id}>
              <Card variant="outlined">
                <CardContent>
                  <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1 }}>
                    <Typography variant="h6" color="text.primary">
                      {it.name}
                    </Typography>
                    <Chip
                      size="small"
                      label={meta.label || it.promotion_status}
                      sx={{ color: "#08152b", background: meta.color, fontWeight: 700 }}
                    />
                  </Stack>
                  <Typography variant="body2" color="text.secondary">
                    {it.symbol}／{it.strategy_key}
                  </Typography>

                  <Stack spacing={0.3} sx={{ mt: 1.5 }}>
                    <Typography variant="caption" color="text.secondary">
                      OOS EV：{fmt(it.oos_expected_value)}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      Paper 勝率：{fmt(stats.win_rate_pct, "%")}{"　"}完整買賣：{fmt(stats.num_round_trips)} 次
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      Paper 報酬：{fmt(stats.return_pct, "%")}
                    </Typography>
                    {it.promotion_reason && (
                      <Typography variant="caption" color="text.secondary">
                        理由：{it.promotion_reason}
                      </Typography>
                    )}
                  </Stack>

                  <Stack direction="row" spacing={1} sx={{ mt: 2 }}>
                    {it.promotion_status === "paper" && (
                      <Button
                        size="small"
                        variant="outlined"
                        disabled={busyId === it.bot_id}
                        onClick={() => propose(it)}
                      >
                        提議上真錢
                      </Button>
                    )}
                    {it.promotion_status === "proposed_live" && (
                      <>
                        <Button
                          size="small"
                          variant="contained"
                          disabled={busyId === it.bot_id}
                          onClick={() => approve(it)}
                        >
                          核准
                        </Button>
                        <Button
                          size="small"
                          color="error"
                          disabled={busyId === it.bot_id}
                          onClick={() => reject(it)}
                        >
                          退回
                        </Button>
                      </>
                    )}
                  </Stack>
                </CardContent>
              </Card>
            </Grid>
          );
        })}
      </Grid>
    </Box>
  );
}
