import { CircleDollarSign, PackageCheck, Tag, X } from "lucide-react";
import { MissionData } from "./types";
import styles from "./mission-studio.module.css";

type Props = { mission: MissionData; onRemoveOwned: (item: string) => void };
type Chip = { icon: typeof Tag; label: string };

const normalize = (value: string) => value.trim().replace(/\s+/g, " ").toLocaleLowerCase();

export default function ExtractedChips({ mission, onRemoveOwned }: Props) {
  const keyRequirements = (mission.key_requirements ?? []).filter(Boolean).slice(0, 6);
  const requirementKeys = new Set(keyRequirements.map(normalize));
  const supportingPreferences = (mission.preferences ?? [])
    .filter((value) => !requirementKeys.has(normalize(value)))
    .slice(0, Math.max(0, 6 - keyRequirements.length));
  const rows: Chip[] = [
    mission.budget ? { icon: CircleDollarSign, label: `Budget · RM ${Number(mission.budget).toLocaleString()}` } : null,
    ...keyRequirements.map((label) => ({ icon: Tag, label })),
    ...supportingPreferences.map((label) => ({ icon: Tag, label })),
  ].filter((item): item is Chip => item !== null);

  return (
    <div className={styles.chipArea}>
      <span className={styles.chipLabel}>AI READS YOUR MISSION</span>
      <div className={styles.chips}>
        {rows.map(({ icon: Icon, label }) => <span className={styles.chip} key={label}><Icon size={13} />{label}</span>)}
        {(mission.owned_items ?? []).map((item) => (
          <button type="button" className={`${styles.chip} ${styles.ownedChip}`} key={item} onClick={() => onRemoveOwned(item)}>
            <PackageCheck size={13} />Already own: {item}<X size={12} />
          </button>
        ))}
        {!rows.length && !(mission.owned_items?.length) && <span className={styles.emptyChip}>Start with a mission — Shopy will surface the details that shape your answer.</span>}
      </div>
    </div>
  );
}
