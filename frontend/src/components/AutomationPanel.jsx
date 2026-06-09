// ============================================================
// AutomationPanel：模式 B 全局自動化規則（可編輯 + 手動觸發）
// ============================================================
// redesign Phase 4 + 後續：規則改吃 DB（automation_config 單列表），前端可編輯。後端：
//   GET  /automation       → 目前規則與名額
//   PUT  /automation       → 編輯規則（只送有帶欄位；改 scan_hour 即時重掛排程）
//   POST /automation/run   → 觸發/預覽一輪自動部署（force / dry_run）
//
// 面板兩態：
//   - 檢視（預設）：唯讀儀表 + 兩顆動作鈕（預覽 / 立即試跑）。
//   - 編輯：展開受控表單改規則，「儲存」呼 PUT；開啟總開關走 ConfirmDialog 二次確認。
//
// 安全：enabled 是「自動駕駛總開關」，與實盤雙閘獨立——開了仍全程 Paper。
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
  TextField,
  FormControlLabel,
  Switch,
} from "@mui/material";

import { api } from "../api";
import Stat from "./Stat";
import ConfirmDialog from "./ConfirmDialog";

// 可編輯欄位定義（label + 後端 key + 數字/開關 + 提示）
const NUMBER_FIELDS = [
  { key: "ev_threshold", label: "EV 門檻", step: "1" },
  { key: "winrate_threshold", label: "勝率門檻（%）", step: "1" },
  { key: "cash_per_bot", label: "配資 / Bot（$）", step: "100" },
  { key: "max_bots", label: "最大 Bot 數", step: "1" },
  { key: "scan_hour", label: "盤前掃描時刻（0~23）", step: "1" },
  { key: "scan_interval_min", label: "探勘間隔（分；0=關）", step: "5" },
];

export default function AutomationPanel({ onChanged }) {
  const [rules, setRules] = useState(null); // GET /automation 的狀態
  const [error, setError] = useState("");
  const [running, setRunning] = useState(false); // 試跑/預覽進行中
  const [result, setResult] = useState(null); // 上一次 run 的回傳（預覽或實跑）
  const [confirmRun, setConfirmRun] = useState(false); // 「立即試跑」確認視窗

  const [editing, setEditing] = useState(false); // 是否在編輯模式
  const [draft, setDraft] = useState(null); // 編輯中的草稿（受控表單）
  const [saving, setSaving] = useState(false);
  const [confirmEnable, setConfirmEnable] = useState(false); // 開啟總開關的二次確認

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

  // 進入編輯：用目前規則填草稿
  function startEdit() {
    setDraft({
      enabled: rules.enabled,
      ev_threshold: rules.ev_threshold,
      winrate_threshold: rules.winrate_threshold,
      cash_per_bot: rules.cash_per_bot,
      max_bots: rules.max_bots,
      scan_hour: rules.scan_hour,
      scan_interval_min: rules.scan_interval_min,
    });
    setResult(null);
    setError("");
    setEditing(true);
  }

  // 真正送出 PUT（開啟總開關時由 ConfirmDialog 先確認再呼這裡）
  async function doSave() {
    setSaving(true);
    setError("");
    try {
      const saved = await api.updateAutomation(draft);
      setRules(saved);
      setEditing(false);
      setDraft(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }

  // 按「儲存」：若是把總開關從關→開，先走確認視窗（語意上等於開自動駕駛）
  function handleSave() {
    if (draft.enabled && !rules.enabled) {
      setConfirmEnable(true);
      return;
    }
    doSave();
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
          盤前掃描達標即自動建 Paper Bot。規則存於資料庫、可在此直接編輯（改 scan_hour
          會即時重掛排程，不必重啟）。開啟總開關仍全程 Paper、與實盤雙閘獨立。
        </Typography>

        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        {!rules ? (
          !error && <CircularProgress size={20} />
        ) : editing ? (
          // ---- 編輯模式：受控表單 ----
          <Box>
            <FormControlLabel
              control={
                <Switch
                  checked={draft.enabled}
                  onChange={(e) =>
                    setDraft({ ...draft, enabled: e.target.checked })
                  }
                />
              }
              label="自動化總開關（開啟＝盤前自動建 Paper Bot）"
            />
            <Box
              sx={{
                display: "grid",
                gridTemplateColumns: { xs: "1fr 1fr", sm: "repeat(3, 1fr)" },
                gap: 2,
                mt: 1,
              }}
            >
              {NUMBER_FIELDS.map((f) => (
                <TextField
                  key={f.key}
                  label={f.label}
                  type="number"
                  size="small"
                  value={draft[f.key]}
                  inputProps={{ step: f.step }}
                  onChange={(e) =>
                    setDraft({ ...draft, [f.key]: e.target.value })
                  }
                />
              ))}
            </Box>
            <Box sx={{ display: "flex", gap: 1, mt: 2 }}>
              <Button
                variant="contained"
                onClick={handleSave}
                disabled={saving}
              >
                儲存
              </Button>
              <Button
                variant="text"
                onClick={() => {
                  setEditing(false);
                  setDraft(null);
                }}
                disabled={saving}
              >
                取消
              </Button>
              {saving && <CircularProgress size={20} />}
            </Box>
          </Box>
        ) : (
          // ---- 檢視模式：唯讀儀表 ----
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
              value={`${Number(rules.winrate_threshold).toFixed(0)}%`}
            />
            <Stat label="配資 / Bot" value={`$${Number(rules.cash_per_bot).toLocaleString()}`} />
            <Stat label="盤前掃描時刻" value={`${rules.scan_hour} 時`} />
            <Stat
              label="探勘間隔"
              value={rules.scan_interval_min > 0 ? `${rules.scan_interval_min} 分` : "關閉"}
            />
            <Stat label="最大 Bot 數" value={rules.max_bots} />
            <Stat
              label="名額（已用 / 上限）"
              value={`${rules.active_bots} / ${rules.max_bots}`}
            />
          </Box>
        )}

        {/* 動作鈕（檢視模式才顯示） */}
        {rules && !editing && (
          <Box sx={{ display: "flex", gap: 1, alignItems: "center", mt: 2 }}>
            <Button variant="outlined" onClick={startEdit} disabled={running}>
              編輯規則
            </Button>
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
        )}

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

      {/* 開啟自動化總開關前先確認 */}
      <ConfirmDialog
        open={confirmEnable}
        title="開啟自動化總開關"
        message="開啟後盤前排程會『無人工確認自動建立 Paper Bot』（全程模擬、與實盤雙閘獨立）。確定開啟？"
        confirmText="開啟並儲存"
        onConfirm={() => {
          setConfirmEnable(false);
          doSave();
        }}
        onClose={() => setConfirmEnable(false)}
      />
    </Card>
  );
}
