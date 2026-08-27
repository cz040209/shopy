import { CircleDollarSign, PackageCheck, Tag, X } from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";
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
    <div className={styles.chipArea} aria-live="polite" aria-label="Mission details detected as you type">
      <span className={styles.chipLabel}>AI READS YOUR MISSION</span>
      <div className={styles.chips}>
        <AnimatePresence initial={false} mode="popLayout">
          {rows.map(({ icon: Icon, label }) => <motion.span className={styles.chip} key={label} initial={{ opacity: 0, scale: 0.84, y: 5 }} animate={{ opacity: 1, scale: 1, y: 0 }} exit={{ opacity: 0, scale: 0.84, y: -4 }} transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}><Icon size={13} />{label}</motion.span>)}
          {(mission.owned_items ?? []).map((item) => (
            <motion.button type="button" className={`${styles.chip} ${styles.ownedChip}`} key={item} onClick={() => onRemoveOwned(item)} initial={{ opacity: 0, scale: 0.84, y: 5 }} animate={{ opacity: 1, scale: 1, y: 0 }} exit={{ opacity: 0, scale: 0.84, y: -4 }} transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}>
              <PackageCheck size={13} />Already own: {item}<X size={12} />
            </motion.button>
          ))}
        </AnimatePresence>
        {!rows.length && !(mission.owned_items?.length) && <span className={styles.emptyChip}>Start with a mission — Shopy will surface the details that shape your answer.</span>}
      </div>
    </div>
  );
}
