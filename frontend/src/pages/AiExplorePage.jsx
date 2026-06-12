// ============================================================
// AiExplorePage：AI 探勘（盤前海選 + 一鍵部署）
// ============================================================
// Phase 9 step-01：原 App tab 1 的內容原樣搬成路由頁，行為不變。

import { useOutletContext } from "react-router-dom";
import RecommendationsPanel from "../components/RecommendationsPanel";

export default function AiExplorePage() {
  const { onDeploy, status } = useOutletContext();
  return (
    <RecommendationsPanel onDeploy={onDeploy} liveArmed={status?.live_armed} />
  );
}
