// ============================================================
// EvolutionPage：進化實驗室（/evolution）
// ============================================================
// Phase 9 step-07：Phase 8 候選策略的審核台——看候選/已驗證、跑驗證管線、
// **人在迴路**晉升（validated→curated）/ 退回（→rejected，附理由）。
// 鐵則：晉升一律由使用者點按觸發；前端不做自動晉升、不重算 EV/驗證。

import { useState, useEffect, useCallback } from "react";
import {
  Box,
  Typography,
  ToggleButton,
  ToggleButtonGroup,
  TextField,
  Grid,
  Stack,
  Button,
  Alert,
} from "@mui/material";
import { api } from "../api";
import KnowledgeCard from "../components/KnowledgeCard";

export default function EvolutionPage() {
  const [status, setStatus] = useState("candidate");
  const [originFilter, setOriginFilter] = useState("all"); // "all" | "paper_feedback" | "manual" | "discovery"
  const [items, setItems] = useState([]);
  const [symbol, setSymbol] = useState("AAPL"); // 單檔驗證用標的（籃子模式忽略）
  const [useBasket, setUseBasket] = useState(true); // 預設完整籃子（與自動驗證路徑同嚴謹度）
  const [busyId, setBusyId] = useState(null);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");

  const load = useCallback(async () => {
    setErr("");
    try {
      setItems(await api.getKnowledge(status));
    } catch (e) {
      setErr(e.message);
    }
  }, [status]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load();
  }, [load]);

  async function runValidate(item) {
    setErr("");
    setMsg("");
    setBusyId(item.id);
    try {
      const summary = await api.validateKnowledge(item.id, {
        use_basket: useBasket,
        symbol: symbol.toUpperCase(),
        days: 365,
      });
      const ev = summary?.oos_metrics?.expected_value;
      setMsg(
        `驗證 #${item.id}：${summary.status ?? "完成"}` +
          (ev != null ? `（OOS EV ${ev}）` : "") +
          (useBasket ? "·完整籃子" : `·單檔 ${symbol.toUpperCase()}`)
      );
      load();
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusyId(null);
    }
  }

  async function promote(item) {
    setErr("");
    setMsg("");
    try {
      await api.promoteKnowledge(item.id);
      setMsg(`已晉升 #${item.id} 進策展庫（curated）`);
      load();
    } catch (e) {
      setErr(e.message);
    }
  }

  async function reject(item) {
    const reason = window.prompt("退回理由（會寫進探討記憶）：", "");
    if (reason === null) return;
    setErr("");
    setMsg("");
    try {
      await api.rejectKnowledge(item.id, reason);
      setMsg(`已退回 #${item.id}`);
      load();
    } catch (e) {
      setErr(e.message);
    }
  }

  return (
    <Box>
      <Typography variant="h4" sx={{ mb: 2 }}>
        進化實驗室
      </Typography>

      <Stack direction="row" spacing={2} alignItems="center" sx={{ mb: 2 }} flexWrap="wrap">
        <ToggleButtonGroup
          size="small"
          exclusive
          value={status}
          onChange={(e, v) => v && setStatus(v)}
        >
          <ToggleButton value="candidate">候選</ToggleButton>
          <ToggleButton value="validated">已驗證</ToggleButton>
          <ToggleButton value="rejected">已退回</ToggleButton>
        </ToggleButtonGroup>
        <ToggleButtonGroup
          size="small"
          exclusive
          value={originFilter}
          onChange={(e, v) => v && setOriginFilter(v)}
        >
          <ToggleButton value="all">全部來源</ToggleButton>
          <ToggleButton value="paper_feedback">從實跑學習</ToggleButton>
          <ToggleButton value="manual">人工建立</ToggleButton>
          <ToggleButton value="discovery">探勘橋</ToggleButton>
        </ToggleButtonGroup>
        <ToggleButtonGroup
          size="small"
          exclusive
          value={useBasket ? "basket" : "single"}
          onChange={(e, v) => v && setUseBasket(v === "basket")}
        >
          <ToggleButton value="basket">完整籃子（嚴謹·較慢）</ToggleButton>
          <ToggleButton value="single">單檔（快）</ToggleButton>
        </ToggleButtonGroup>
        <TextField
          size="small"
          label="單檔標的（籃子模式忽略）"
          value={symbol}
          onChange={(e) => setSymbol(e.target.value)}
          disabled={useBasket}
          sx={{ width: 190 }}
        />
      </Stack>

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
        {(originFilter === "all" ? items : items.filter((i) => i.origin === originFilter)).length === 0 && (
          <Grid item xs={12}>
            <Typography variant="caption" color="text.secondary">
              這一層沒有策略。
            </Typography>
          </Grid>
        )}
        {(originFilter === "all" ? items : items.filter((i) => i.origin === originFilter)).map((item) => (
          <Grid item xs={12} sm={6} md={4} key={item.id}>
            <KnowledgeCard
              item={item}
              actions={
                <Stack direction="row" spacing={1}>
                  {item.status === "candidate" && (
                    <Button
                      size="small"
                      variant="outlined"
                      disabled={busyId === item.id}
                      onClick={() => runValidate(item)}
                    >
                      {busyId === item.id ? "驗證中…" : "驗證"}
                    </Button>
                  )}
                  {item.status === "validated" && (
                    <Button
                      size="small"
                      variant="contained"
                      onClick={() => promote(item)}
                    >
                      晉升
                    </Button>
                  )}
                  {item.status !== "rejected" && (
                    <Button
                      size="small"
                      color="error"
                      onClick={() => reject(item)}
                    >
                      退回
                    </Button>
                  )}
                </Stack>
              }
            />
          </Grid>
        ))}
      </Grid>
    </Box>
  );
}
