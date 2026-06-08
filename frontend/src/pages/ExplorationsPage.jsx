// ============================================================
// ExplorationsPage：探討 / 檢討頁（/explorations）
// ============================================================
// Phase 9 step-05：把 explorations/ 檔案記憶（LLM 事後檢討）做成可瀏覽頁：
//   左側列路標清單、右側讀某篇檢討內容。**唯讀**（檢討由 chat/postmortem 產生）。
// 一律經 api.getExplorations / getExploration（後端走防穿越服務），不在前端拼路徑。
// 內容用輕量 pre-wrap 顯示（與助手聊天一致），不引重型 markdown 依賴。

import { useState, useEffect } from "react";
import {
  Box,
  Typography,
  Paper,
  List,
  ListItemButton,
  ListItemText,
  Alert,
  Grid,
} from "@mui/material";
import { api } from "../api";

export default function ExplorationsPage() {
  const [entries, setEntries] = useState([]);
  const [selected, setSelected] = useState(null); // { name, content }
  const [err, setErr] = useState("");

  useEffect(() => {
    api
      .getExplorations()
      // eslint-disable-next-line react-hooks/set-state-in-effect
      .then(setEntries)
      .catch((e) => setErr(e.message));
  }, []);

  async function openEntry(entry) {
    setErr("");
    try {
      setSelected(await api.getExploration(entry.file));
    } catch (e) {
      setErr(e.message);
    }
  }

  return (
    <Box>
      <Typography variant="h4" sx={{ mb: 2 }}>
        探討 / 檢討
      </Typography>

      {err && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setErr("")}>
          {err}
        </Alert>
      )}

      <Grid container spacing={2}>
        {/* 左：路標清單 */}
        <Grid item xs={12} md={4}>
          <Paper variant="outlined">
            <List dense disablePadding>
              {entries.length === 0 && (
                <Box sx={{ p: 2 }}>
                  <Typography variant="caption" color="text.secondary">
                    還沒有任何檢討紀錄。到回測歷史按「總結這次錯在哪」就會產生。
                  </Typography>
                </Box>
              )}
              {entries.map((e) => (
                <ListItemButton
                  key={e.file}
                  selected={selected?.name === e.file}
                  onClick={() => openEntry(e)}
                >
                  <ListItemText
                    primary={`run#${e.run_id} · ${e.strategy} / ${e.symbol}`}
                    secondary={e.summary}
                    primaryTypographyProps={{ variant: "subtitle2", noWrap: true }}
                    secondaryTypographyProps={{ variant: "caption", noWrap: true }}
                  />
                </ListItemButton>
              ))}
            </List>
          </Paper>
        </Grid>

        {/* 右：內容 */}
        <Grid item xs={12} md={8}>
          <Paper variant="outlined" sx={{ p: 2, minHeight: 240 }}>
            {selected ? (
              <Box
                component="pre"
                sx={{
                  m: 0,
                  whiteSpace: "pre-wrap",
                  wordBreak: "break-word",
                  fontFamily: '"IBM Plex Mono", monospace',
                  fontSize: 13,
                  lineHeight: 1.7,
                }}
              >
                {selected.content}
              </Box>
            ) : (
              <Typography variant="caption" color="text.secondary">
                從左側挑一篇檢討來閱讀。
              </Typography>
            )}
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
}
