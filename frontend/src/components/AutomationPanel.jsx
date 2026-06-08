// ============================================================
// AutomationPanel：模式 B 全局自動化規則（唯讀狀態 + 手動觸發）
// ============================================================
// redesign Phase 4 的前端收尾。後端已有：
//   GET  /automation       → 目前規則與名額
//   POST /automation/run   → 觸發/預覽一輪自動部署（force / dry_run）
//
// 規則本身由 .env 的 AUTO_DEPLOY_* 設定、runtime 唯讀，所以這面板「只看不改」：
//   - 唯讀儀表：總開關、EV/勝率門檻、配資、名額（active_bots / max_bots）
//   - 兩顆動作鈕：「預覽（dry-run）」只試算會部署誰、不建；
//                「立即試跑一輪」會真的建 Paper Bot（故走 ConfirmDialog 確認）。
//
// props:
//   onChanged()：試跑成功後通知父層 reload（讓儀表板 Bot 列表更新）

import { useEffect, useState } from "react";
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
import Stat from "./Stat";
import ConfirmDialog from "./ConfirmDialog";

export default function AutomationPanel({ onChanged }) {
  const [rules, setRules] = useState(null); // GET /automation 的狀態
  const [error, setError] = useState("");
  const [running, setRunning] = useState(false); // 試跑/預覽進行中
  const [result, setResult] = useState(null); // 上一次 run 的回傳（預覽或實跑）
  const [confirmRun, setConfirmRun] = useState(false); // 「立即試跑」確認視窗

  // 掛載時自抓一次狀態（自包含，比照其他面板慣例）
  useEffect(() => {
    let alive = true;
    api
      .getAutomation()
      .then((r) => alive && setRules(r))
      .catch((e) => alive && setError(e.message));
    return () => {
      alive = false;
    };
  }, []);

  // 觸發一輪（dry=true 只預覽不建）。force 一律 true：方便沒開總開關也能手動驗證。
  async function run(dry) {
    setRunning(true);
    setError("");
    setResult(null);
    try {
      const r = await api.runAutomation({ force: true, dry_run: dry });
      setResult({ dry, ...r });
      if (!dry) {
        // 真的建了 Bot：重抓名額狀態 + 通知父層 reload
        api.getAutomation().then(setRules).catch(() => {});
        onChanged?.();
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setRunning(false);
    }
  }

  return (
    <Card sx={{ mb: 3 }}>
      <CardContent>
        <Box
          sx={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            mb: 1,
          }}
        >
          <Typography variant="h6">全自動護欄（模式 B）</Typography>
          {rules &&
            (rules.enabled ? (
              <Chip size="small" color="success" label="自動化開啟" />
            ) : (
              <Chip size="small" label="已關閉" />
            ))}
        </Box>

        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          盤前掃描達標即自動建 Paper Bot。規則由 <code>.env</code> 的{" "}
          <code>AUTO_DEPLOY_*</code> 設定、程式唯讀——要改門檻請編輯 <code>.env</code>{" "}
          後重啟後端。此處只看狀態並可手動試跑一輪。
        </Typography>

        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        {rules ? (
          <Box
            sx={{
              display: "grid",
              gridTemplateColumns: { xs: "1fr 1fr", sm: "repeat(3, 1fr)" },
              gap: 2,
            }}
          >
            <Stat label="EV 門檻" value={rules.ev_threshold} />
            <Stat
              label="勝率門檻"
              value={`${(rules.winrate_threshold * 100).toFixed(0)}%`}
            />
            <Stat label="配資 / Bot" value={`$${Number(rules.cash_per_bot).toLocaleString()}`} />
            <Stat label="盤前掃描時刻" value={`${rules.scan_hour} 時`} />
            <Stat label="最大 Bot 數" value={rules.max_bots} />
            <Stat
              label="名額（已用 / 上限）"
              value={`${rules.active_bots} / ${rules.max_bots}`}
            />
          </Box>
        ) : (
          !error && <CircularProgress size={20} />
        )}

        {/* 動作鈕 */}
        <Box sx={{ display: "flex", gap: 1, alignItems: "center", mt: 2 }}>
          <Button variant="outlined" onClick={() => run(true)} disabled={running}>
            預覽（dry-run）
          </Button>
          <Button
            variant="contained"
            onClick={() => setConfirmRun(true)}
            disabled={running}
          >
            立即試跑一輪
          </Button>
          {running && <CircularProgress size={20} />}
        </Box>

        {/* 上一次 run 的結果摘要 */}
        {result && (
          <Alert severity={result.dry ? "info" : "success"} sx={{ mt: 2 }}>
            {result.dry ? "預覽：" : "已試跑："}
            {(() => {
              // dry-run 看「會部署誰」(planned)；實跑看「真的建了誰」(deployed)
              const list = result.dry ? result.planned : result.deployed;
              if (Array.isArray(list) && list.length > 0) {
                const names = list
                  .map((d) => `${d.symbol}（${d.strategy_key}）`)
                  .join("、");
                return result.dry
                  ? `${list.length} 檔達標：${names}`
                  : `建了 ${list.length} 個 Paper Bot：${names}`;
              }
              return "本輪沒有達標的策略，未部署任何 Bot。";
            })()}
          </Alert>
        )}
      </CardContent>

      {/* 真的建 Paper Bot 前先確認 */}
      <ConfirmDialog
        open={confirmRun}
        title="立即試跑一輪自動部署"
        message="會依目前規則海選並『真的建立 Paper Bot』（全程模擬，不送真錢）。確定試跑？"
        confirmText="試跑"
        onConfirm={() => {
          setConfirmRun(false);
          run(false);
        }}
        onClose={() => setConfirmRun(false)}
      />
    </Card>
  );
}
