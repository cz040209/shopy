import { motion } from "framer-motion";
import { ArrowUpRight, Plus } from "lucide-react";
import { MissionData } from "./types";
import ExtractedChips from "./ExtractedChips";
import styles from "./mission-studio.module.css";

type Props = {
  request: string;
  mission: MissionData;
  busy: boolean;
  onRequestChange: (value: string) => void;
  onLaunch: () => void;
  onRemoveOwned: (item: string) => void;
};

export default function MissionInputPanel({ request, mission, busy, onRequestChange, onLaunch, onRemoveOwned }: Props) {
  return (
    <section className={styles.inputPanel} aria-labelledby="mission-input-title">
      <div className={styles.sectionIntro}>
        <span>01 · SHAPE YOUR BRIEF</span>
        <h2 id="mission-input-title">What should Shopy make happen?</h2>
        <p>Use natural language. Include a budget, what you own, and what matters most if you know them.</p>
      </div>
      <div className={styles.inputSurface}>
        <textarea
          value={request}
          onChange={(event) => onRequestChange(event.target.value)}
          placeholder="Build me a calm WFH setup under RM2,000. I already own a laptop and prefer warm wood."
          rows={2}
        />
        <motion.button
          type="button"
          className={styles.launchButton}
          disabled={busy || !request.trim()}
          onClick={onLaunch}
          whileHover={busy ? undefined : { y: -2, scale: 1.015 }}
          whileTap={busy ? undefined : { scale: 0.98 }}
        >
          {busy ? "Working…" : "Run mission"}<ArrowUpRight size={17} />
        </motion.button>
      </div>
      <ExtractedChips mission={mission} onRemoveOwned={onRemoveOwned} />
      <button className={styles.addOwned} type="button" onClick={() => onRequestChange(`${request}${request ? " " : ""}I already own `)}>
        <Plus size={16} /> Add something you own
      </button>
    </section>
  );
}
