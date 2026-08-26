import { motion } from "framer-motion";
import { Check, LoaderCircle } from "lucide-react";
import styles from "./mission-studio.module.css";

const steps = ["Understanding mission", "Searching products", "Analyzing reviews", "Checking compatibility", "Optimizing bundle", "Auditing result"];

type Props = { busy: boolean; complete: boolean; activeStep: number };

export default function AIProgressPanel({ busy, complete, activeStep }: Props) {
  const active = complete ? steps.length : activeStep;

  return (
    <aside className={styles.progressPanel} aria-live="polite">
      <div className={styles.progressHeading}>
        <span>02 · AI WORKSPACE</span>
        <h2>{busy ? "Shopy is building it." : complete ? "Your answer is ready." : "See the reasoning unfold."}</h2>
        <p>{busy ? "Live activity from your shopping agents." : "Start the mission to watch each specialist do its part."}</p>
      </div>
      <ol>
        {steps.map((step, index) => {
          const isDone = complete || (busy && index < active);
          const isActive = busy && index === active;
          return (
            <motion.li
              layout
              key={step}
              className={isDone ? styles.done : isActive ? styles.active : ""}
              animate={isActive
                ? { opacity: 1, scale: 1, x: 0 }
                : { opacity: isDone ? 0.78 : 0.42, scale: 0.985, x: 0 }}
              transition={{ duration: 0.42, ease: [0.22, 1, 0.36, 1] }}
            >
              <i>{isDone ? <Check size={15} /> : isActive ? <LoaderCircle size={15} /> : index + 1}</i>
              <span>{step}</span>
              {isActive && <b><em /> LIVE NOW</b>}
            </motion.li>
          );
        })}
      </ol>
    </aside>
  );
}
