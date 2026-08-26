import { CircleDollarSign, PackageCheck, Sparkles, Tag, X } from "lucide-react";
import { MissionData } from "./types";
import styles from "./mission-workspace.module.css";

type Props = { mission: MissionData; onRemoveOwned: (item: string) => void };

export default function ExtractedChips({ mission, onRemoveOwned }: Props) {
  const rows = [
    mission.budget ? { icon: CircleDollarSign, label: `Budget · RM ${Number(mission.budget).toLocaleString()}` } : null,
    mission.mission_type ? { icon: Sparkles, label: mission.mission_type.replaceAll("_", " ") } : null,
    ...(mission.preferences ?? []).slice(0, 3).map((label) => ({ icon: Tag, label })),
  ].filter(Boolean) as { icon: typeof Tag; label: string }[];
  return <div className={styles.chipArea}><span className={styles.chipLabel}>AI READS YOUR MISSION</span><div className={styles.chips}>{rows.map(({ icon: Icon, label }) => <span className={styles.chip} key={label}><Icon size={13} />{label}</span>)}{(mission.owned_items ?? []).map((item) => <button type="button" className={`${styles.chip} ${styles.ownedChip}`} key={item} onClick={() => onRemoveOwned(item)}><PackageCheck size={13} />Already own: {item}<X size={12} /></button>)}{!rows.length && !(mission.owned_items?.length) && <span className={styles.emptyChip}>Tell us what you need — Shopy will pull out the useful details.</span>}</div></div>;
}
