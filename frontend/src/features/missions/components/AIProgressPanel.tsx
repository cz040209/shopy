import { AnimatePresence, motion } from "framer-motion";
import { Check, LoaderCircle, Sparkles } from "lucide-react";
import styles from "./mission-studio.module.css";

const steps = ["Understanding mission", "Searching products", "Evaluating catalog ratings", "Checking compatibility", "Optimizing bundle", "Auditing result"];
const focusOrbitPoses = [
  { x: 0, y: 76, z: 110, scale: 1, rotateY: 0, opacity: 1 },
  { x: 255, y: 38, z: 12, scale: 0.8, rotateY: -43, opacity: 0.68 },
  { x: 310, y: -88, z: -86, scale: 0.64, rotateY: -58, opacity: 0.38 },
  { x: 0, y: -138, z: -130, scale: 0.57, rotateY: 0, opacity: 0.26 },
  { x: -310, y: -88, z: -86, scale: 0.64, rotateY: 58, opacity: 0.38 },
  { x: -255, y: 38, z: 12, scale: 0.8, rotateY: 43, opacity: 0.68 },
];

type Props = { busy: boolean; complete: boolean; activeStep: number; focus?: boolean };

export default function AIProgressPanel({ busy, complete, activeStep, focus = false }: Props) {
  const active = complete ? steps.length : activeStep;
  const orbitSteps = [0, 1, 2].map((offset) => (activeStep + offset) % steps.length);

  return (
    <aside className={`${styles.progressPanel} ${focus ? styles.progressPanelFocus : ""}`} aria-live="polite">
      {!focus && <div className={styles.progressHeading}>
        <span>02 · EXECUTION WORKSPACE</span>
        <h2>{busy ? "Building your recommendation." : complete ? "Recommendation verified." : "A clear view of the process."}</h2>
        <p>{busy ? "Live progress across the recommendation workflow." : "Start the mission to follow each verification stage."}</p>
      </div>}
      {busy ? (
        <div className={styles.processingOrbit} aria-label={`Step ${activeStep + 1}: ${steps[activeStep]}`}>
          {!focus && <><div className={styles.orbitHalo} aria-hidden="true" />
            <div className={styles.orbitCaption}><Sparkles size={14} /> PROCESSING · {String(activeStep + 1).padStart(2, "0")} / {String(steps.length).padStart(2, "0")}</div></>}
          <div className={styles.orbitStage}>
            {focus ? steps.map((step, stepIndex) => {
              const position = (stepIndex - activeStep + steps.length) % steps.length;
              const isFront = position === 0;
              return <motion.div
                className={`${styles.orbitCard} ${isFront ? styles.orbitCardFront : ""}`}
                key={step}
                initial={false}
                animate={focusOrbitPoses[position]}
                transition={{ duration: 1.28, ease: [0.32, 0.72, 0, 1] }}
              >
                <span className={styles.orbitNumber}>{String(stepIndex + 1).padStart(2, "0")}</span>
                <strong>{step}</strong>
                {isFront && <span className={styles.orbitLive}><LoaderCircle size={14} /> IN FOCUS</span>}
              </motion.div>;
            }) : <AnimatePresence initial={false} mode="popLayout">
                {orbitSteps.map((stepIndex, position) => {
                  const isFront = position === 0;
                  return <motion.div className={`${styles.orbitCard} ${isFront ? styles.orbitCardFront : position === 1 ? styles.orbitCardRight : styles.orbitCardLeft}`} key={`${stepIndex}-${position}`} initial={{ opacity: 0, rotateY: position === 1 ? -58 : 58, z: -100, scale: 0.72 }} animate={{ opacity: isFront ? 1 : 0.48, rotateY: isFront ? 0 : position === 1 ? -51 : 51, z: isFront ? 56 : -64, scale: isFront ? 1 : 0.76 }} exit={{ opacity: 0, rotateY: position === 1 ? 72 : -72, z: -150, scale: 0.62 }} transition={{ duration: 0.86, ease: [0.22, 1, 0.36, 1] }}><span className={styles.orbitNumber}>{String(stepIndex + 1).padStart(2, "0")}</span><strong>{steps[stepIndex]}</strong>{isFront && <span className={styles.orbitLive}><LoaderCircle size={14} /> LIVE</span>}</motion.div>;
                })}
              </AnimatePresence>}
          </div>
          {!focus && <p><span /> The front card advances as each specialist hands off to the next.</p>}
        </div>
      ) : (
        <ol>
          {steps.map((step, index) => {
            const isDone = complete || (busy && index < active);
            const isActive = busy && index === active;
            return (
              <motion.li layout key={step} className={isDone ? styles.done : isActive ? styles.active : ""}>
                <i>{isDone ? <Check size={15} /> : index + 1}</i>
                <span>{step}</span>
              </motion.li>
            );
          })}
        </ol>
      )}
    </aside>
  );
}
