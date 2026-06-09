// ============================================================
// EditPresetDialog：編輯策略方案的彈出視窗（取代 window.prompt）
// ============================================================
// 原本改名／調參數用兩個 window.prompt，醜又容易打錯 JSON。改成站內 Dialog：
//   名稱 + 策略下拉 + 股票 + 參數（JSON）多行輸入，JSON 即時驗證、錯誤就停用「儲存」。
//
// props：
//   preset — 正在編輯的方案（null = 視窗關閉）
//   onClose — 關閉
//   onSave(payload) — 父層負責真正呼叫 api.updatePreset（payload 已含完整欄位）

import { useState, useEffect } from "react";
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  MenuItem,
  Button,
  Box,
} from "@mui/material";
import { STRATEGIES } from "../constants";

export default function EditPresetDialog({ preset, onClose, onSave }) {
  const [name, setName] = useState("");
  const [strategyKey, setStrategyKey] = useState("ma_crossover");
  const [symbol, setSymbol] = useState("");
  const [paramsStr, setParamsStr] = useState("{}");

  // 開窗（preset 變非 null）時，用該方案的值初始化表單。
  // 這是「開窗時把外部資料同步進表單」的正當用途，故關閉 set-state-in-effect 誤報。
  useEffect(() => {
    if (!preset) return;
    /* eslint-disable react-hooks/set-state-in-effect */
    setName(preset.name || "");
    setStrategyKey(preset.strategy_key || "ma_crossover");
    setSymbol(preset.symbol || "");
    setParamsStr(JSON.stringify(preset.params || {}, null, 2));
    /* eslint-enable react-hooks/set-state-in-effect */
  }, [preset]);

  // 驗證
  const nameErr = !name.trim();
  const symbolErr = !symbol.trim();
  let jsonErr = false;
  try {
    JSON.parse(paramsStr || "{}");
  } catch {
    jsonErr = true;
  }
  const hasError = nameErr || symbolErr || jsonErr;

  function handleSave() {
    if (hasError) return;
    onSave({
      name: name.trim(),
      strategy_key: strategyKey,
      symbol: symbol.trim().toUpperCase(),
      params: JSON.parse(paramsStr || "{}"),
      is_favorite: preset?.is_favorite,
      notes: preset?.notes,
    });
  }

  return (
    <Dialog open={!!preset} onClose={onClose} fullWidth maxWidth="xs">
      <DialogTitle>編輯方案</DialogTitle>
      <DialogContent>
        <Box sx={{ display: "grid", gap: 2, mt: 1 }}>
          <TextField
            label="方案名稱"
            required
            value={name}
            error={nameErr}
            helperText={nameErr ? "名稱不能空白" : " "}
            onChange={(e) => setName(e.target.value)}
          />
          <TextField
            select
            label="策略"
            value={strategyKey}
            onChange={(e) => setStrategyKey(e.target.value)}
          >
            {STRATEGIES.map((s) => (
              <MenuItem key={s.value} value={s.value}>
                {s.label}
              </MenuItem>
            ))}
          </TextField>
          <TextField
            label="股票代號"
            required
            value={symbol}
            error={symbolErr}
            helperText={symbolErr ? "請填股票代號" : " "}
            onChange={(e) => setSymbol(e.target.value)}
          />
          <TextField
            label="策略參數（JSON）"
            multiline
            minRows={3}
            value={paramsStr}
            error={jsonErr}
            helperText={
              jsonErr ? "不是合法 JSON" : '例如 {"period": 14}'
            }
            onChange={(e) => setParamsStr(e.target.value)}
            sx={{ "& textarea": { fontFamily: "var(--font-mono)" } }}
          />
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>取消</Button>
        <Button variant="contained" onClick={handleSave} disabled={hasError}>
          儲存
        </Button>
      </DialogActions>
    </Dialog>
  );
}
