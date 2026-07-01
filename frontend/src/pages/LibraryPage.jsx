// ============================================================
// LibraryPage：策略知識庫（/library）
// ============================================================
// Phase 9 step-07：Phase 8 知識庫的唯讀策展庫 + 排行呈現。
//   理論 / 場景 / 使用時機 / OOS 指標 / 狀態親和性，依 OOS EV 排序。
// 唯讀：不做晉升/退回（那在 /evolution）；前端不重算 EV。

import { useState, useEffect, useCallback } from "react";
import {
  Box,
  Typography,
  ToggleButton,
  ToggleButtonGroup,
  Grid,
  Alert,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
} from "@mui/material";
import { api } from "../api";
import KnowledgeCard from "../components/KnowledgeCard";

export default function LibraryPage() {
  // 看哪一層：策展庫 / 已驗證 / 候選 / 已退回（補齊，不再藏中途與淘汰項）
  const [status, setStatus] = useState("curated");
  const [items, setItems] = useState([]);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  // 部署到標的：哪一筆 curated 正在部署 + 標的輸入框 + 進行中旗標
  const [deployTarget, setDeployTarget] = useState(null);
  const [symbolsInput, setSymbolsInput] = useState("SPY,QQQ,AAPL");
  const [deploying, setDeploying] = useState(false);

  const load = useCallback(async () => {
    setErr("");
    try {
      // 排行端點已依 OOS EV 由高到低排序
      setItems(await api.getKnowledgeRanking(status));
    } catch (e) {
      setErr(e.message);
    }
  }, [status]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load();
  }, [load]);

  // 把一筆 curated 策略部署到多檔股票（每檔各建一個 paper bot；建好未啟動，人再去監控中心開）。
  async function confirmDeploy() {
    const k = deployTarget;
    const symbols = symbolsInput
      .split(",")
      .map((s) => s.trim().toUpperCase())
      .filter(Boolean);
    if (symbols.length === 0) {
      setErr("請至少填一個標的");
      return;
    }
    setErr("");
    setMsg("");
    setDeploying(true);
    try {
      const r = await api.deployKnowledge(k.id, { symbols, trade_amount: 1000 });
      setMsg(
        `已為「${k.name}」建立 ${r.deployed.length} 個 paper bot（${symbols.join("、")}）。` +
          "建好未啟動，到監控中心按啟動開始虛擬交易。"
      );
      setDeployTarget(null);
    } catch (e) {
      setErr(e.message);
    } finally {
      setDeploying(false);
    }
  }

  return (
    <Box>
      <Typography variant="h4" sx={{ mb: 2 }}>
        策略知識庫
      </Typography>

      <ToggleButtonGroup
        size="small"
        exclusive
        value={status}
        onChange={(e, v) => v && setStatus(v)}
        sx={{ mb: 2 }}
      >
        <ToggleButton value="curated">策展庫</ToggleButton>
        <ToggleButton value="validated">已驗證</ToggleButton>
        <ToggleButton value="candidate">候選</ToggleButton>
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
              這一層還沒有策略。看完整漏斗（含候選 / 退回與淘汰理由）到「探勘漏斗」頁。
            </Typography>
          </Grid>
        )}
        {items.map((item) => (
          <Grid item xs={12} sm={6} md={4} key={item.id}>
            <KnowledgeCard
              item={item}
              actions={
                item.status === "curated" ? (
                  <Button size="small" variant="contained" onClick={() => setDeployTarget(item)}>
                    部署到標的
                  </Button>
                ) : null
              }
            />
          </Grid>
        ))}
      </Grid>

      {/* 部署到標的：curated 策略 → 每檔股票一個 paper bot（虛擬交易找最佳模型） */}
      <Dialog open={!!deployTarget} onClose={() => !deploying && setDeployTarget(null)} fullWidth maxWidth="xs">
        <DialogTitle>部署「{deployTarget?.name}」到標的</DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            逗號分隔多檔股票，每檔各建一個 paper bot（用這個策略對該股票虛擬交易）。
            建好未啟動，到監控中心按啟動。
          </Typography>
          <TextField
            autoFocus
            fullWidth
            size="small"
            label="標的（逗號分隔）"
            value={symbolsInput}
            onChange={(e) => setSymbolsInput(e.target.value)}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeployTarget(null)} disabled={deploying}>
            取消
          </Button>
          <Button variant="contained" onClick={confirmDeploy} disabled={deploying}>
            {deploying ? "部署中…" : "部署"}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
