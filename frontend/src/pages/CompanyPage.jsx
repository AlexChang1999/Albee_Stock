// ============================================================
// CompanyPage：公司戰情頁（Phase 10 step-01）
// ============================================================
// 把後端 /company/overview 聚合的各部門現況畫成「一頁看到整間 AI 公司」。
//   - 純呈現層：只顯示後端數字，不在前端重算 EV / 勝率、不做任何交易或部署動作。
//   - 每張「部門卡」對應一個公司角色，連到對應的既有頁去實際操作。
// 顏色一律吃 theme / NEON（深藍主題下寫死 hex 會在深底上隱形）。

import { useState, useEffect, useCallback } from "react";
import { Link as RouterLink } from "react-router-dom";
import {
  Box,
  Grid,
  Card,
  CardContent,
  Typography,
  Button,
  Chip,
  Stack,
  Alert,
  Divider,
} from "@mui/material";
import { api } from "../api";
import Stat from "../components/Stat";

// 金額格式化：後端帳戶欄位是字串；離線（null）時顯示破折號。
function fmtMoney(v) {
  if (v === null || v === undefined || v === "") return "—";
  const n = Number(v);
  return Number.isNaN(n) ? "—" : `$${n.toLocaleString()}`;
}

// 把後端各「跑一次」端點回的統計 dict 壓成一句中文摘要（只挑有值的鍵）。
function summarizeResult(r) {
  if (!r || typeof r !== "object") return "完成";
  const labels = {
    inserted: "新收", built: "建候選", discarded: "丟棄", processed: "處理",
    validated: "通過", rejected: "退回", deployed_knowledge: "部署策略",
    bots_created: "建Bot", reviewed: "考核", culled: "汰弱", skipped: "跳過",
    fits_updated: "更新fit", failed: "失敗",
  };
  const parts = [];
  for (const [k, label] of Object.entries(labels)) {
    if (r[k] != null && r[k] !== 0) parts.push(`${label} ${r[k]}`);
  }
  if (parts.length === 0) return r.note || r.message || "完成（無新增）";
  return parts.join("、") + (r.note ? `（${r.note}）` : "");
}

// 部門卡外殼：標題 + 狀態 chip + 內容 + 「前往」連結。
function DeptCard({ title, role, chip, to, linkLabel, children }) {
  return (
    <Card sx={{ height: "100%" }}>
      <CardContent>
        <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 1 }}>
          <Box>
            <Typography variant="h6">{title}</Typography>
            <Typography variant="caption" color="text.secondary">
              {role}
            </Typography>
          </Box>
          {chip}
        </Stack>
        <Divider sx={{ mb: 2 }} />
        {children}
        {to && (
          <Button
            component={RouterLink}
            to={to}
            size="small"
            sx={{ mt: 2 }}
          >
            {linkLabel || "前往 →"}
          </Button>
        )}
      </CardContent>
    </Card>
  );
}

export default function CompanyPage() {
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");
  const [scanning, setScanning] = useState(false);
  const [scanMsg, setScanMsg] = useState("");
  // 探勘流水線「跑一次」：哪顆鈕正在跑（互斥）+ 結果摘要訊息
  const [busyAction, setBusyAction] = useState("");
  const [actionMsg, setActionMsg] = useState("");

  const load = useCallback(async () => {
    try {
      setData(await api.getCompanyOverview());
    } catch (e) {
      setErr(e.message);
    }
  }, []);

  // 立刻掃一輪：強制跑一輪海選選標的（不必等盤中排程），掃完重抓戰情頁看新機會。
  const handleScan = useCallback(async () => {
    setScanning(true);
    setScanMsg("");
    try {
      const r = await api.scanOpportunities();
      setScanMsg(r.message || "掃描完成");
      await load(); // 重抓 overview，機會清單更新
    } catch (e) {
      setScanMsg(`掃描失敗：${e.message}`);
    } finally {
      setScanning(false);
    }
  }, [load]);

  // 探勘流水線逐關手動推進：跑完重抓 overview，漏斗數字當場跳動（擬人操作）。
  const runAction = useCallback(
    async (key, label, fn) => {
      setBusyAction(key);
      setActionMsg("");
      try {
        const r = await fn();
        setActionMsg(`${label}：${summarizeResult(r)}`);
        await load();
      } catch (e) {
        setActionMsg(`${label}失敗：${e.message}`);
      } finally {
        setBusyAction("");
      }
    },
    [load]
  );

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load();
  }, [load]);

  if (err) {
    return (
      <Alert severity="error" onClose={() => setErr("")}>
        {err}
      </Alert>
    );
  }
  if (!data) {
    return <Typography color="text.secondary">載入中…</Typography>;
  }

  const {
    account,
    bots,
    automation,
    circuit_breaker: breaker,
    decisions,
    opportunities = [],
    discovery_funnel: funnel = null,
  } = data;

  return (
    <Box>
      <Typography variant="h4" sx={{ mb: 2 }}>
        公司戰情
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        一頁看到整間 AI 公司：各部門現況聚合，點卡片前往對應頁操作。
      </Typography>

      <Grid container spacing={2}>
        {/* Bot 艦隊（策略員）：帳戶 + 啟用中／總數 */}
        <Grid item xs={12} sm={6} md={4}>
          <DeptCard
            title="Bot 艦隊"
            role="策略員 · 在跑的交易機器人"
            to="/"
            linkLabel="監控中心 →"
            chip={
              <Chip
                size="small"
                label={`${bots.active}/${bots.total} 啟用`}
                color={bots.active > 0 ? "success" : "default"}
              />
            }
          >
            <Stack direction="row" spacing={3}>
              <Stat label="總資產" value={fmtMoney(account?.portfolio_value)} />
              <Stat label="購買力" value={fmtMoney(account?.buying_power)} />
            </Stack>
            {!account && (
              <Typography variant="caption" color="text.secondary">
                （未連線 Alpaca，帳戶數字暫不可得）
              </Typography>
            )}
          </DeptCard>
        </Grid>

        {/* 自動化（模式 B）：總開關 + 雙重門檻 + 名額 */}
        <Grid item xs={12} sm={6} md={4}>
          <DeptCard
            title="自動化部署"
            role="模式 B · 盤前自動建 Bot 規則"
            to="/"
            linkLabel="調整規則 →"
            chip={
              <Chip
                size="small"
                label={automation.enabled ? "自動駕駛中" : "已關閉"}
                color={automation.enabled ? "success" : "default"}
              />
            }
          >
            <Stack direction="row" spacing={3} sx={{ mb: 1 }}>
              <Stat label="EV 門檻" value={automation.ev_threshold} />
              <Stat label="勝率門檻" value={`${automation.winrate_threshold}%`} />
              <Stat label="名額" value={`${bots.active}/${automation.max_bots}`} />
            </Stack>
          </DeptCard>
        </Grid>

        {/* 風控熔斷：組合回撤熔斷狀態 */}
        <Grid item xs={12} sm={6} md={4}>
          <DeptCard
            title="風控熔斷"
            role="組合回撤熔斷 · 只擋進不擋出"
            chip={
              <Chip
                size="small"
                label={breaker.tripped ? "熔斷中" : "正常"}
                color={breaker.tripped ? "error" : "success"}
              />
            }
          >
            <Stack direction="row" spacing={3}>
              <Stat label="目前權益" value={fmtMoney(breaker.equity_now)} />
              <Stat label="權益峰值" value={fmtMoney(breaker.equity_peak)} />
            </Stack>
          </DeptCard>
        </Grid>

        {/* 策略主管：回測 EV 榜 */}
        <Grid item xs={12} sm={6} md={4}>
          <DeptCard
            title="策略主管"
            role="拿歷史回測 · 含成本 / 隔日成交"
            to="/backtest-runs"
            linkLabel="EV 榜 →"
          >
            <Typography variant="body2" color="text.secondary">
              依樣本外 EV 排名的回測歷史，挑冠軍一律看 OOS。
            </Typography>
          </DeptCard>
        </Grid>

        {/* 回測主管：組合進化實驗室 */}
        <Grid item xs={12} sm={6} md={4}>
          <DeptCard
            title="回測主管"
            role="決定哪些上交 · 組合進化"
            to="/evolution"
            linkLabel="進化實驗室 →"
          >
            <Typography variant="body2" color="text.secondary">
              蒐集多策略 → 整合組合 → OOS 驗證 → 人在迴路策展。
            </Typography>
          </DeptCard>
        </Grid>

        {/* 決策審計：最近決策軌跡 */}
        <Grid item xs={12} sm={6} md={4}>
          <DeptCard
            title="決策審計"
            role="每筆買 / 賣 / 觀望都可追溯"
            to="/decisions"
            linkLabel="決策軌跡 →"
            chip={
              <Chip size="small" label={`最近 ${decisions.length} 筆`} color="default" />
            }
          >
            {decisions.length === 0 ? (
              <Typography variant="caption" color="text.secondary">
                還沒有決策紀錄。
              </Typography>
            ) : (
              <Stack spacing={0.5}>
                {decisions.slice(0, 3).map((d) => (
                  <Typography key={d.id} variant="caption" color="text.secondary">
                    {d.symbol}：{d.action}（{d.reason}）
                  </Typography>
                ))}
              </Stack>
            )}
          </DeptCard>
        </Grid>

        {/* 常駐探勘：機會清單（依 OOS EV 排名的候選，好策略不漏掉） */}
        <Grid item xs={12} sm={6} md={4}>
          <DeptCard
            title="常駐探勘"
            role="機會清單 · 盤中持續收，好策略不漏掉"
            chip={
              <Chip
                size="small"
                label={`${opportunities.length} 個候選`}
                color={opportunities.length > 0 ? "success" : "default"}
              />
            }
          >
            {opportunities.length === 0 ? (
              <Typography variant="caption" color="text.secondary">
                尚無候選（盤中掃描累積中）。
              </Typography>
            ) : (
              <Stack spacing={0.5}>
                {opportunities.slice(0, 5).map((o) => (
                  <Typography key={o.id} variant="caption" color="text.secondary">
                    {o.symbol} · {o.strategy_key}{"　"}OOS EV {o.oos_expected_value ?? "—"}
                  </Typography>
                ))}
              </Stack>
            )}

            {/* 立刻掃一輪：不必等盤中排程，按了強制對 watchlist 跑一輪海選選標的。
                watchlist 多檔 + 回測較重，可能要跑數十秒。 */}
            <Button
              variant="outlined"
              size="small"
              onClick={handleScan}
              disabled={scanning}
              sx={{ mt: 2 }}
            >
              {scanning ? "掃描中…（可能數十秒）" : "🔎 立刻掃一輪"}
            </Button>
            {scanMsg && (
              <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 1 }}>
                {scanMsg}
              </Typography>
            )}
          </DeptCard>
        </Grid>

        {/* 探勘漏斗（Phase 12 step-04）：raw → candidate → validated → curated，
            人只看最後一道閘——validated 待審徽章 + 跳既有 LibraryPage 策展 */}
        {funnel && (
          <Grid item xs={12} sm={6} md={4}>
            <DeptCard
              title="探勘漏斗 · 操作台"
              role="收料 → 候選 → 驗證 → 入庫 · 人逐關手動推進"
              to="/funnel"
              linkLabel="看漏斗全貌 →"
              chip={
                <Chip
                  size="small"
                  label={`待審 ${funnel.knowledge.validated}`}
                  color={funnel.knowledge.validated > 0 ? "warning" : "default"}
                />
              }
            >
              <Stack direction="row" spacing={3} sx={{ mb: 1 }}>
                <Stat label="raw 收料" value={funnel.raw.new + funnel.raw.triaged + funnel.raw.built + funnel.raw.discarded} />
                <Stat label="candidate" value={funnel.knowledge.candidate} />
                <Stat label="validated" value={funnel.knowledge.validated} />
                <Stat label="curated" value={funnel.knowledge.curated} />
              </Stack>
              <Typography variant="caption" color="text.secondary">
                淘汰率 {funnel.rejection_rate_pct ?? "—"}
                {funnel.rejection_rate_pct != null && "%"}（高是健康的：大部分點子過不了 OOS 閘是預期）
              </Typography>

              {/* 排程關閉中：每個 AI 角色一顆「跑一次」鈕，逐關推進，數字當場跳動 */}
              <Divider sx={{ my: 1.5 }} />
              <Typography variant="caption" color="text.secondary" sx={{ display: "block", mb: 1 }}>
                人工逐關推進（排程關閉中）：
              </Typography>
              <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
                {[
                  ["collect", "收料", () => api.runCollectorScan()],
                  ["discover", "探勘", () => api.runDiscovery()],
                  ["validate", "驗證", () => api.runValidateBatch()],
                  ["deploy", "部署", () => api.runAutoDeployKnowledge()],
                  ["review", "審查", () => api.runBotReview()],
                ].map(([key, label, fn]) => (
                  <Button
                    key={key}
                    size="small"
                    variant="outlined"
                    disabled={!!busyAction}
                    onClick={() => runAction(key, label, fn)}
                  >
                    {busyAction === key ? "…" : `▶ ${label}`}
                  </Button>
                ))}
              </Stack>
              {actionMsg && (
                <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 1 }}>
                  {actionMsg}
                </Typography>
              )}
            </DeptCard>
          </Grid>
        )}
      </Grid>
    </Box>
  );
}
