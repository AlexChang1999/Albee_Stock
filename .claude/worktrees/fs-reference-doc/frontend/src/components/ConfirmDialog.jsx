// ============================================================
// ConfirmDialog：通用的「確認 / 取消」彈出視窗
// ============================================================
// 取代瀏覽器原生的 window.confirm()，好處是長相能跟全站風格一致、可自訂文字。
//
// 設計成「通用」元件：不綁死「刪除 Bot」這件事，任何需要二次確認的動作都能用。
// props：
//   open      — 是否打開（true/false）
//   title     — 標題文字
//   message   — 內文（要確認什麼）
//   confirmText — 確認鈕文字（預設「確認」）
//   confirmColor — 確認鈕顏色（預設 "error"，因為多半用在刪除這種危險動作）
//   onConfirm — 按下確認時要跑的函式
//   onClose   — 按下取消 / 點背景關閉時要跑的函式

import {
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
} from "@mui/material";

export default function ConfirmDialog({
  open,
  title,
  message,
  confirmText = "確認",
  confirmColor = "error",
  onConfirm,
  onClose,
}) {
  return (
    <Dialog open={open} onClose={onClose} maxWidth="xs" fullWidth>
      <DialogTitle>{title}</DialogTitle>
      <DialogContent>
        <DialogContentText>{message}</DialogContentText>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>取消</Button>
        <Button variant="contained" color={confirmColor} onClick={onConfirm}>
          {confirmText}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
