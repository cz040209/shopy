import { ArrowUpRight, Plus, Sparkles } from "lucide-react";
import { MissionData } from "./types";
import ExtractedChips from "./ExtractedChips";
import styles from "./mission-workspace.module.css";

type Props = { request: string; mission: MissionData; busy: boolean; onRequestChange: (value: string) => void; onLaunch: () => void; onRemoveOwned: (item: string) => void };

export default function MissionInputPanel({ request, mission, busy, onRequestChange, onLaunch, onRemoveOwned }: Props) {
  return <section className={styles.inputPanel} aria-labelledby="mission-input-title"><div className={styles.sectionIntro}><span>02 · DEFINE THE OUTCOME</span><h2 id="mission-input-title">What are we making happen?</h2></div><div className={styles.inputSurface}><Sparkles className={styles.inputSparkle} size={22} /><textarea value={request} onChange={(event) => onRequestChange(event.target.value)} placeholder="e.g. Build me a calm WFH desk setup under RM2,000. I already own a laptop and like warm wood." rows={3} /><button type="button" className={styles.launchButton} disabled={busy || !request.trim()} onClick={onLaunch}>{busy ? "Reading mission…" : "Start mission"}<ArrowUpRight size={17} /></button></div><ExtractedChips mission={mission} onRemoveOwned={onRemoveOwned} /><button className={styles.addOwned} type="button" onClick={() => onRequestChange(`${request}${request ? " " : ""}I already own `)}><Plus size={14} /> Add something you own</button></section>;
}
