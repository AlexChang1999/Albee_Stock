// ============================================================
// AssistantDrawer：全站思考助手抽屜（Phase 9 step-08）
// ============================================================
// 原本塞在右側 StrategyWorkbench 區4 的「Claude 助手聊天」，搬成全站可開的抽屜：
// 右下浮動鈕開關，任何頁面都能叫出來。沿用既有 api.sendChat / api.postmortem，
// 助手鐵則不變（只「思考」：不下單、不啟停 Bot、不跑回測）。

import { useState } from "react";
import {
  Box,
  Drawer,
  Fab,
  Typography,
  TextField,
  Button,
  Stack,
  IconButton,
  CircularProgress,
  Alert,
} from "@mui/material";
import { api } from "../api";
import { NEON } from "../theme";

export default function AssistantDrawer() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState([]);
  const [chatInput, setChatInput] = useState("");
  const [runId, setRunId] = useState("");
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  async function handleSend() {
    const text = chatInput.trim();
    if (!text) return;
    const next = [...messages, { role: "user", content: text }];
    setMessages(next);
    setChatInput("");
    setLoading(true);
    setErr("");
    try {
      const r = await api.sendChat(next);
      setMessages((prev) => [...prev, { role: "assistant", content: r.reply }]);
    } catch (e) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  }

  // 對某筆回測請 Claude 檢討（沿用工作台原本「總結這次錯在哪」邏輯）
  async function handlePostmortem() {
    const id = Number(runId);
    if (!id) {
      setErr("請輸入要檢討的回測 ID");
      return;
    }
    setLoading(true);
    setErr("");
    try {
      const r = await api.postmortem(id);
      const refs = (r.references || []).map((f) => {
        const m = f.match(/run-0*(\d+)-/);
        return m ? `run#${m[1]}` : f;
      });
      const refLine = refs.length ? `\n\n📎 參考過去探討：${refs.join("、")}` : "";
      setMessages((prev) => [
        ...prev,
        { role: "user", content: `請檢討回測 #${id}` },
        { role: "assistant", content: r.postmortem + refLine },
      ]);
      setRunId("");
    } catch (e) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      {/* 右下浮動開關鈕 */}
      <Fab
        color="primary"
        onClick={() => setOpen(true)}
        sx={{ position: "fixed", bottom: 24, right: 24, zIndex: 1200 }}
      >
        💬
      </Fab>

      <Drawer anchor="right" open={open} onClose={() => setOpen(false)}>
        <Box sx={{ width: { xs: 320, sm: 380 }, p: 2, height: "100%", display: "flex", flexDirection: "column" }}>
          <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 1 }}>
            <Typography variant="h6" sx={{ color: NEON.cyan }}>
              思考助手
            </Typography>
            <IconButton size="small" onClick={() => setOpen(false)}>
              ✕
            </IconButton>
          </Stack>
          <Typography variant="caption" color="text.secondary">
            問策略設計 / 調參建議，或填回測 ID 做事後檢討。助手只思考，不下單、不跑回測。
          </Typography>

          {err && (
            <Alert severity="error" sx={{ my: 1 }} onClose={() => setErr("")}>
              {err}
            </Alert>
          )}

          {/* 訊息區 */}
          <Box
            sx={{
              flex: 1,
              minHeight: 0,
              overflowY: "auto",
              my: 1,
              display: "flex",
              flexDirection: "column",
              gap: 0.5,
            }}
          >
            {messages.length === 0 && (
              <Typography variant="caption" color="text.secondary">
                （需在後端啟動本機 Ollama，或在 .env 改接其他免費供應商。）
              </Typography>
            )}
            {messages.map((m, i) => (
              <Box
                key={i}
                sx={{
                  alignSelf: m.role === "user" ? "flex-end" : "flex-start",
                  maxWidth: "85%",
                  px: 1.2,
                  py: 0.8,
                  borderRadius: 2,
                  whiteSpace: "pre-wrap",
                  fontSize: 13,
                  background:
                    m.role === "user"
                      ? "rgba(77,163,255,0.14)"
                      : "rgba(255,255,255,0.05)",
                }}
              >
                {m.content}
              </Box>
            ))}
            {loading && <CircularProgress size={18} sx={{ alignSelf: "center" }} />}
          </Box>

          {/* 事後檢討（輸入回測 ID） */}
          <Stack direction="row" spacing={1} sx={{ mb: 1 }}>
            <TextField
              size="small"
              type="number"
              label="回測 ID"
              value={runId}
              onChange={(e) => setRunId(e.target.value)}
              sx={{ width: 110 }}
            />
            <Button size="small" variant="outlined" onClick={handlePostmortem} disabled={loading}>
              檢討
            </Button>
          </Stack>

          {/* 聊天輸入 */}
          <Stack direction="row" spacing={1}>
            <TextField
              size="small"
              fullWidth
              placeholder="輸入訊息…"
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleSend();
                }
              }}
            />
            <Button variant="contained" size="small" onClick={handleSend} disabled={loading}>
              送出
            </Button>
          </Stack>
        </Box>
      </Drawer>
    </>
  );
}
