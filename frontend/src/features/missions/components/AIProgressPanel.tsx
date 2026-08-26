import { Check, LoaderCircle } from "lucide-react";
import styles from "./mission-workspace.module.css";

const steps = ["Understanding mission", "Searching products", "Analyzing reviews", "Checking compatibility", "Optimizing bundle", "Auditing result"];

export default function AIProgressPanel({ busy, complete }: { busy: boolean; complete: boolean }) {
  const active = busy ? 2 : complete ? steps.length : 0;
  return <aside className={styles.progressPanel} aria-live="polite"><div><span>03 · AI MISSION WORKSPACE</span><h2>{busy ? "Shopy is on it." : complete ? "Your mission is ready." : "Your plan will take shape here."}</h2></div><ol>{steps.map((step, index) => <li key={step} className={index < active ? styles.done : index === active && busy ? styles.active : ""}><i>{index < active || complete ? <Check size={13} /> : index === active && busy ? <LoaderCircle size={13} /> : index + 1}</i>{step}</li>)}</ol></aside>;
}
