// ============================================================
// DecisionFeed：決策原因即時流（機器人的思考日誌）
// ============================================================
// 每輪決策（含「黃金交叉未成立，觀望」這種沒動作的）即時滑入頂部——
// 像看機器人邊跑邊寫日記，一眼確認系統真的在思考。
//
// 資料來源兩段式：
//   1. 開頁播種：GET /bots/decisions/recent（DB 裡最近 N 筆，重整不丟歷史）
//   2. 即時追加：useBotActivity 的 feed（WS decision 事件，最新在前）
// 兩邊用 bot_id + 時間去重後合併，feed 在前（較新）。
//
// 歷史查詢職責仍在 DecisionsPage（選 Bot 看完整軌跡），這裡只管「現在」。

import { useEffect, useState } from "react";
import { Box, Card, CardContent, Chip, Stack, Typography } from "@mui/material";
import { api } from "../api";
import { actionMeta } from "../utils/decisionMeta";

const KEEP_MAX = 50; // 流上保留的最大則數

/** 把 WS 事件與 API 列統一成同一種列格式（顯示層只認這個）。 */
function normalizeWs(ev) {
  return {
    key: `ws-${ev.bot_id}-${ev.ts}`,
    botName: ev.bot_name || `Bot #${ev.bot_id}`,
    symbol: ev.symbol,
    action: ev.decision?.action,
    reason: ev.decision?.reason || ev.detail || "",
    price: ev.decision?.price,
    at: ev.ts ? new Date(ev.ts * 1000) : new Date(),
    live: true, // 即時事件 → 播滑入動畫
  };
}

function normalizeApi(row) {
  return {
    key: `db-${row.id}`,
    botName: row.bot_name || `Bot #${row.bot_id}`,
    symbol: row.symbol,
    action: row.action,
    reason: row.reason || "",
    price: row.price,
    at: row.created_at ? new Date(row.created_at) : null,
    live: false, // 播種的歷史 → 不播動畫
  };
}

export default function DecisionFeed({ feed = [] }) {
  const [seed, setSeed] = useState([]);

  // 開頁先從 DB 播種最近決策（失敗就靜默：feed 仍能靠 WS 慢慢長出來）
  useEffect(() => {
    let mounted = true;
    api
      .getRecentDecisions()
      .then((rows) => mounted && setSeed(rows.map(normalizeApi)))
      .catch(() => {});
    return () => {
      mounted = false;
    };
  }, []);

  // 合併：WS 即時事件在前（較新），再接 DB 播種；同秒同 Bot 視為重複丟掉
  const wsRows = feed.map(normalizeWs);
  const seen = new Set(
    wsRows.map((r) => `${r.botName}-${r.at && Math.floor(r.at.getTime() / 1000)}`)
  );
  const rows = [
    ...wsRows,
    ...seed.filter(
      (r) => !seen.has(`${r.botName}-${r.at && Math.floor(r.at.getTime() / 1000)}`)
    ),
  ].slice(0, KEEP_MAX);

  return (
    <Card sx={{ mb: 3 }}>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          決策即時流
        </Typography>
        {rows.length === 0 ? (
          <Typography variant="caption" color="text.secondary">
            還沒有決策紀錄——Bot 跑起來後，每輪決策（含觀望）會即時出現在這裡。
          </Typography>
        ) : (
          <Stack spacing={0.75} sx={{ maxHeight: 320, overflowY: "auto" }}>
            {rows.map((r) => {
              const meta = actionMeta(r.action);
              return (
                <Box
                  key={r.key}
                  sx={{
                    display: "flex",
                    alignItems: "center",
                    gap: 1,
                    // 只有即時事件播滑入（keyframes 在 BotActivityStatus 全域註冊）
                    ...(r.live && { animation: "feed-slide-in 0.3s ease-out" }),
                  }}
                >
                  <Typography
                    variant="caption"
                    color="text.secondary"
                    sx={{ minWidth: 64, flexShrink: 0 }}
                  >
                    {r.at
                      ? r.at.toLocaleTimeString("zh-TW", { hour12: false })
                      : "—"}
                  </Typography>
                  <Typography
                    variant="caption"
                    fontWeight={600}
                    noWrap
                    sx={{ minWidth: 90, maxWidth: 120, flexShrink: 0 }}
                    title={r.botName}
                  >
                    {r.botName}
                  </Typography>
                  <Chip
                    size="small"
                    variant="outlined"
                    label={meta.label}
                    sx={{ color: meta.color, borderColor: meta.color, flexShrink: 0 }}
                  />
                  <Typography variant="caption" color="text.secondary" noWrap title={r.reason}>
                    {r.reason}
                    {r.price != null && `（$${r.price}）`}
                  </Typography>
                </Box>
              );
            })}
          </Stack>
        )}
      </CardContent>
    </Card>
  );
}
