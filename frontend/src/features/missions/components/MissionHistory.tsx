import { Clock3 } from "lucide-react";
import { MissionHistoryItem } from "./types";
import styles from "./mission-studio.module.css";

export default function MissionHistory({ entries, onRestore }: { entries: MissionHistoryItem[]; onRestore: (label: string) => void }) {
  return <aside className={styles.history}><span><Clock3 size={14} /> MISSION HISTORY</span>{entries.length ? <div>{entries.map((entry) => <button type="button" key={entry.id} onClick={() => onRestore(entry.label)}><strong>{entry.label}</strong><small>{entry.at} · RM {entry.total.toLocaleString("en-MY", { maximumFractionDigits: 0 })}</small></button>)}</div> : <p>Your finished missions will stay here for this session.</p>}</aside>;
}
