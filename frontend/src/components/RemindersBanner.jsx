// ============================================================
// RemindersBanner：主動提醒橫幅（Phase 5 選配）
// ============================================================
// 從 GET /reminders 抓「值得主動關注」的待辦，彙整成一條橫幅顯示：
//   - review_negative_ev：回測 EV 為負且還沒檢討 → 提醒去請助手分析。
//   - deploy_good_strategy：標為好策略但還沒實跑 → 提醒可一鍵轉 Bot。
// 無事項時不顯示任何東西（回 null），不佔版面。
//
// props:
//   signal：父層每次資料變動（建 Bot / 跑回測）就 +1，用來觸發重抓提醒。

import { useState, useEffect } from "react";
import { Alert, AlertTitle, List, ListItem, ListItemText } from "@mui/material";
import { api } from "../api";

// 不同提醒類型的橫幅嚴重度（負 EV 偏警告、好策略待實跑偏資訊）
const SEVERITY = {
  review_negative_ev: "warning",
  deploy_good_strategy: "info",
};

export default function RemindersBanner({ signal = 0 }) {
  const [reminders, setReminders] = useState([]);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const res = await api.getReminders();
        if (alive) setReminders(res.reminders || []);
      } catch {
        // 提醒是輔助功能，抓不到就安靜略過，不干擾主要操作
        if (alive) setReminders([]);
      }
    })();
    return () => {
      alive = false;
    };
  }, [signal]);

  if (reminders.length === 0) return null;

  // 有「負 EV 未檢討」就整條用 warning，否則 info
  const hasWarning = reminders.some((r) => r.type === "review_negative_ev");

  return (
    <Alert severity={hasWarning ? "warning" : "info"} sx={{ mb: 2 }}>
      <AlertTitle>有 {reminders.length} 則待辦提醒</AlertTitle>
      <List dense disablePadding>
        {reminders.map((r, i) => (
          <ListItem key={`${r.type}-${r.run_id}-${i}`} disableGutters sx={{ py: 0 }}>
            <ListItemText
              primary={r.message}
              primaryTypographyProps={{
                variant: "body2",
                color: SEVERITY[r.type] === "warning" ? "warning.main" : "text.secondary",
              }}
            />
          </ListItem>
        ))}
      </List>
    </Alert>
  );
}
