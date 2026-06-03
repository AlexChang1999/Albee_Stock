// ============================================================
// FundamentalsPanel：基本面 / 財報 / 新聞面板
// ============================================================
// 輸入股票代號 → 一次抓「公司基本資料 + 財報三表 + 新聞 + 配息/分割」並顯示。
// 資料來源是後端 /fundamentals/* 端點（底層用免費的 yfinance）。

import { useState } from "react";
import {
  Box,
  Card,
  CardContent,
  Typography,
  TextField,
  Button,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Link,
  Alert,
  Chip,
  ToggleButton,
  ToggleButtonGroup,
} from "@mui/material";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import { api } from "../api";
import { formatCompact } from "../utils/number";

// 公司基本資料裡，這些欄位是「大數字」，用縮寫顯示比較好讀
const COMPACT_KEYS = new Set([
  "marketCap",
  "fullTimeEmployees",
  "fiftyTwoWeekHigh",
  "fiftyTwoWeekLow",
]);

// 一張財報表的呈現：科目當列、各期間當欄
function StatementTable({ records }) {
  if (!records || records.length === 0) {
    return <Typography color="text.secondary">查無資料</Typography>;
  }
  // 用第一期的科目當列名（各期科目一致）
  const lineItems = Object.keys(records[0].items);
  return (
    <Box sx={{ overflowX: "auto" }}>
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>會計科目</TableCell>
            {records.map((r) => (
              <TableCell key={r.period} align="right">
                {r.period}
              </TableCell>
            ))}
          </TableRow>
        </TableHead>
        <TableBody>
          {lineItems.map((item) => (
            <TableRow key={item}>
              <TableCell>{item}</TableCell>
              {records.map((r) => (
                <TableCell key={r.period} align="right">
                  {formatCompact(r.items[item])}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Box>
  );
}

export default function FundamentalsPanel() {
  const [symbolInput, setSymbolInput] = useState("AAPL");
  const [symbol, setSymbol] = useState("");
  const [period, setPeriod] = useState("annual"); // 年度 / 季度
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [profile, setProfile] = useState(null);
  const [financials, setFinancials] = useState(null);
  const [news, setNews] = useState(null);
  const [actions, setActions] = useState(null);

  // 一次抓四種資料
  async function load(sym, per = period) {
    setError("");
    setLoading(true);
    try {
      // 並行抓，較快（四個請求互不相依）
      const [p, f, n, a] = await Promise.all([
        api.getProfile(sym),
        api.getFinancials(sym, per),
        api.getNews(sym),
        api.getActions(sym),
      ]);
      setProfile(p);
      setFinancials(f);
      setNews(n);
      setActions(a);
      setSymbol(sym);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  // 只重抓財報（切換年度/季度時用，不必重抓其他三種）
  async function reloadFinancials(per) {
    setPeriod(per);
    if (!symbol) return;
    try {
      setFinancials(await api.getFinancials(symbol, per));
    } catch (e) {
      setError(e.message);
    }
  }

  return (
    <Box>
      {/* 查詢列 */}
      <Box sx={{ display: "flex", gap: 1, mb: 2 }}>
        <TextField
          size="small"
          label="股票代號"
          value={symbolInput}
          onChange={(e) => setSymbolInput(e.target.value)}
          placeholder="例如：AAPL、TSLA、NVDA"
        />
        <Button
          variant="contained"
          disabled={loading}
          onClick={() => load(symbolInput.toUpperCase())}
        >
          {loading ? "查詢中…" : "查詢"}
        </Button>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {/* 公司基本資料 */}
      {profile && (
        <Card sx={{ mb: 2 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              📋 {profile.fields.longName || symbol}（{symbol}）
            </Typography>
            <Box
              sx={{
                display: "grid",
                gridTemplateColumns: { xs: "1fr 1fr", md: "repeat(3, 1fr)" },
                gap: 1,
              }}
            >
              {Object.entries(profile.fields)
                .filter(([k]) => k !== "longName" && k !== "longBusinessSummary" && k !== "website")
                .map(([key, value]) => (
                  <Box key={key}>
                    <Typography variant="caption" color="text.secondary">
                      {profile.labels[key] || key}
                    </Typography>
                    <Typography variant="body2">
                      {COMPACT_KEYS.has(key) ? formatCompact(value) : String(value)}
                    </Typography>
                  </Box>
                ))}
            </Box>
            {profile.fields.website && (
              <Typography variant="body2" sx={{ mt: 1 }}>
                官網：
                <Link href={profile.fields.website} target="_blank" rel="noopener">
                  {profile.fields.website}
                </Link>
              </Typography>
            )}
            {profile.fields.longBusinessSummary && (
              <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                {profile.fields.longBusinessSummary}
              </Typography>
            )}
          </CardContent>
        </Card>
      )}

      {/* 財報三表 */}
      {financials && (
        <Card sx={{ mb: 2 }}>
          <CardContent>
            <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 1 }}>
              <Typography variant="h6">📊 財報三表</Typography>
              <ToggleButtonGroup
                size="small"
                exclusive
                value={period}
                onChange={(e, v) => v && reloadFinancials(v)}
              >
                <ToggleButton value="annual">年度</ToggleButton>
                <ToggleButton value="quarterly">季度</ToggleButton>
              </ToggleButtonGroup>
            </Box>
            {[
              ["損益表", financials.income],
              ["資產負債表", financials.balance],
              ["現金流量表", financials.cashflow],
            ].map(([title, records]) => (
              <Accordion key={title}>
                <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                  {title}
                </AccordionSummary>
                <AccordionDetails>
                  <StatementTable records={records} />
                </AccordionDetails>
              </Accordion>
            ))}
          </CardContent>
        </Card>
      )}

      {/* 配息 / 分割 */}
      {actions && (
        <Card sx={{ mb: 2 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              💰 配息 / 分割
            </Typography>
            <Typography variant="body2" color="text.secondary">
              歷史配息 {actions.dividends.length} 筆、股票分割 {actions.splits.length} 次
            </Typography>
            {/* 只列最近 5 筆配息 */}
            {actions.dividends.slice(-5).reverse().map((d) => (
              <Chip
                key={d.date}
                label={`${d.date}：$${Number(d.amount).toFixed(2)}`}
                size="small"
                sx={{ mr: 0.5, mt: 0.5 }}
              />
            ))}
          </CardContent>
        </Card>
      )}

      {/* 新聞 */}
      {news && news.news.length > 0 && (
        <Card sx={{ mb: 2 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              📰 相關新聞
            </Typography>
            {news.news.map((n, i) => (
              <Box key={i} sx={{ mb: 1 }}>
                <Link href={n.link} target="_blank" rel="noopener" variant="body2">
                  {n.title || "（無標題）"}
                </Link>
                {n.publisher && (
                  <Typography variant="caption" color="text.secondary" sx={{ ml: 1 }}>
                    — {n.publisher}
                  </Typography>
                )}
              </Box>
            ))}
          </CardContent>
        </Card>
      )}
    </Box>
  );
}
