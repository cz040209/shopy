import { motion } from "framer-motion";
import { LoaderCircle, Plus, Send } from "lucide-react";
import { useEffect, useRef } from "react";
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
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const resizeTextarea = (element: HTMLTextAreaElement) => {
    element.style.height = "auto";
    element.style.height = `${Math.min(element.scrollHeight, 132)}px`;
  };

  useEffect(() => {
    if (textareaRef.current) resizeTextarea(textareaRef.current);
  }, [request]);

  return (
    <section className={styles.inputPanel} aria-labelledby="mission-input-title">
      <div className={styles.sectionIntro}>
        <span>01 · DEFINE YOUR MISSION</span>
        <h2 id="mission-input-title">Set the brief. We’ll handle the details.</h2>
        <p>Describe the outcome, budget, what you already own, and the priorities that should guide the recommendation.</p>
      </div>
      <div className={styles.inputSurface}>
        <textarea
          ref={textareaRef}
          value={request}
          onChange={(event) => {
            resizeTextarea(event.currentTarget);
            onRequestChange(event.target.value);
          }}
          placeholder="Build me a calm WFH setup under RM2,000. I already own a laptop and prefer warm wood."
          rows={1}
        />
        <motion.button
          type="button"
          className={styles.launchButton}
          disabled={busy || !request.trim()}
          onClick={onLaunch}
          aria-label={busy ? "Shopy is building your mission" : "Submit mission"}
          title={busy ? "Shopy is building your mission" : "Submit mission"}
          whileHover={busy ? undefined : { y: -2, scale: 1.015 }}
          whileTap={busy ? undefined : { scale: 0.98 }}
        >
          {busy ? <LoaderCircle size={19} /> : <Send size={19} />}
        </motion.button>
      </div>
      <ExtractedChips mission={mission} onRemoveOwned={onRemoveOwned} />
      <button className={styles.addOwned} type="button" onClick={() => onRequestChange(`${request}${request ? " " : ""}I already own `)}>
        <Plus size={16} /> Add something you own
      </button>
    </section>
  );
}
