import { Gem, Heart, Palette, TrendingDown, Star } from "lucide-react";
import styles from "./mission-studio.module.css";

const actions = [
  {
    label: "Make it cheaper",
    prompt: "Recompose the current recommendation for a lower total price while preserving its shopping outcome and product-role coverage.",
    icon: TrendingDown,
  },
  {
    label: "Make it better",
    prompt: "Recompose the current recommendation to prioritize verified quality and performance while preserving its shopping outcome and product-role coverage.",
    icon: Gem,
  },
  {
    label: "Make it prettier",
    prompt: "Recompose the current recommendation to prioritize verified appearance, design, and style evidence while preserving its shopping outcome and product-role coverage.",
    icon: Palette,
  },
  {
    label: "More comfortable",
    prompt: "Recompose the current recommendation to prioritize verified comfort and ergonomic evidence while preserving its shopping outcome and product-role coverage.",
    icon: Heart,
  },
  {
    label: "Better reviewed",
    prompt: "Recompose the current recommendation to prioritize stronger verified ratings and review evidence while preserving its shopping outcome and product-role coverage.",
    icon: Star,
  },
];

export default function OptimizationActions({ disabled, onPick }: { disabled: boolean; onPick: (prompt: string) => void }) {
  return (
    <section className={styles.optimizations}>
      <span>RECOMPOSE THIS MISSION</span>
      <div>
        {actions.map(({ label, prompt, icon: Icon }, index) => (
          <button
            className={styles[`actionTone${index % 5}`]}
            type="button"
            key={label}
            disabled={disabled}
            onClick={() => onPick(prompt)}
          >
            <Icon size={15} />
            {label}
          </button>
        ))}
      </div>
    </section>
  );
}
