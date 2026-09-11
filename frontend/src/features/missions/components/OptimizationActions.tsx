import { Star } from "lucide-react";
import type { MissionRefinement } from "./types";
import styles from "./mission-studio.module.css";

const actions: Array<{ label: string; icon: typeof Star } & MissionRefinement> = [
  {
    label: "Better reviewed",
    prompt: "Recompose the current recommendation to prioritize stronger verified ratings and review evidence while preserving its shopping outcome and product-role coverage.",
    inputPayload: { optimization: { mode: "higher_rating", selection_criteria: [
      { field: "rating_average", operator: "higher_than_reference", value: null, weight: 10 },
    ] } },
    icon: Star,
  },
];

export default function OptimizationActions({ disabled, onPick }: { disabled: boolean; onPick: (refinement: MissionRefinement) => void }) {
  return (
    <section className={styles.optimizations}>
      <span>RECOMPOSE THIS MISSION</span>
      <div>
        {actions.map(({ label, icon: Icon, ...refinement }, index) => (
          <button
            className={styles[`actionTone${index % 5}`]}
            type="button"
            key={label}
            disabled={disabled}
            onClick={() => onPick(refinement)}
          >
            <Icon size={15} />
            {label}
          </button>
        ))}
      </div>
    </section>
  );
}
