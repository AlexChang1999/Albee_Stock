// ============================================================
// AccountCard：帳戶資訊卡片
// ============================================================
// props：
//   account — 後端回傳的帳戶物件（還沒載入時是 null）

import { Card, CardContent, Typography, Box, Skeleton } from "@mui/material";
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
          // Skeleton 載入態（E3）：先畫四格灰塊佔位，載到資料換成真數字
          <Box
            sx={{
              display: "grid",
              gridTemplateColumns: { xs: "1fr 1fr", sm: "repeat(4, 1fr)" },
              gap: 2,
            }}
            aria-label="帳戶資訊載入中"
          >
            {[0, 1, 2, 3].map((i) => (
              <Box key={i}>
                <Skeleton width={48} height={16} />
                <Skeleton width={90} height={28} />
              </Box>
            ))}
          </Box>
        )}
      </CardContent>
    </Card>
  );
}
