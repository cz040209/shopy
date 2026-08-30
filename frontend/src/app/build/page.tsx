import { Suspense } from "react";
import MissionWorkspace from "@/features/missions/components/MissionWorkspace";

export default function BuildPage() {
  return <Suspense fallback={null}><MissionWorkspace /></Suspense>;
}
