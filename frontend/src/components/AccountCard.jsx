// ============================================================
// AccountCard：帳戶資訊卡片
// ============================================================
// props：
//   account — 後端回傳的帳戶物件（還沒載入時是 null）

import { Card, CardContent, Typography, Box } from "@mui/material";
import Stat from "./Stat";
import { money } from "../utils/number";

export default function AccountCard({ account }) {
  return (
    <Card sx={{ mb: 3 }}>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          帳戶資訊
        </Typography>
        {account ? (
          <Box
            sx={{
              display: "grid",
              gridTemplateColumns: { xs: "1fr 1fr", sm: "repeat(4, 1fr)" },
              gap: 2,
            }}
          >
            <Stat label="狀態" value={account.status} />
            <Stat label="現金" value={money(account.cash)} />
            <Stat label="購買力" value={money(account.buying_power)} />
            <Stat label="總值" value={money(account.portfolio_value)} />
          </Box>
        ) : (
          <Typography color="text.secondary">
            載入中…（若一直沒出現，請確認後端已啟動）
          </Typography>
        )}
      </CardContent>
    </Card>
  );
}
