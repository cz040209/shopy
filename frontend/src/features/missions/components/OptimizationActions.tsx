import { Gem, Heart, Palette, TrendingDown, Star } from "lucide-react";
import styles from "./mission-studio.module.css";

const actions = [{ label: "Make it cheaper", prompt: "Make it cheaper", icon: TrendingDown }, { label: "Make it better", prompt: "Prioritize quality and performance", icon: Gem }, { label: "Make it prettier", prompt: "Make it prettier", icon: Palette }, { label: "More comfortable", prompt: "Make it more comfortable", icon: Heart }, { label: "Better reviewed", prompt: "Prioritize better reviewed options", icon: Star }];

export default function OptimizationActions({ disabled, onPick }: { disabled: boolean; onPick: (prompt: string) => void }) {
  return <section className={styles.optimizations}><span>RECOMPOSE THIS MISSION</span><div>{actions.map(({ label, prompt, icon: Icon }) => <button type="button" key={label} disabled={disabled} onClick={() => onPick(prompt)}><Icon size={15} />{label}</button>)}</div></section>;
}
