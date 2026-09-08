import { Gem, Heart, Palette, TrendingDown, Star } from "lucide-react";
import type { MissionRefinement } from "./types";
import styles from "./mission-studio.module.css";

const actions: Array<{ label: string; icon: typeof TrendingDown } & MissionRefinement> = [
  {
    label: "Make it cheaper",
    prompt: "Recompose the current recommendation for a lower total price while preserving its shopping outcome and product-role coverage.",
    inputPayload: { optimization: { mode: "lower_price", selection_criteria: [
      { field: "price", operator: "lower_than_reference", value: null, weight: 10 },
    ] } },
    icon: TrendingDown,
  },
  {
    label: "Make it better",
    prompt: "Recompose the current recommendation to prioritize verified quality and performance while preserving its shopping outcome and product-role coverage.",
    inputPayload: { optimization: { mode: "quality_performance", selection_criteria: [
      { field: "catalog_facts", operator: "prefer_match", value: "quality performance", weight: 10 },
    ] } },
    icon: Gem,
  },
  {
    label: "Make it prettier",
    prompt: "Recompose the current recommendation to prioritize verified appearance, design, and style evidence while preserving its shopping outcome and product-role coverage.",
    inputPayload: { optimization: { mode: "appearance_style", selection_criteria: [
      { field: "catalog_facts", operator: "prefer_match", value: "appearance design style", weight: 10 },
    ] } },
    icon: Palette,
  },
  {
    label: "More comfortable",
    prompt: "Recompose the current recommendation to prioritize verified comfort and ergonomic evidence while preserving its shopping outcome and product-role coverage.",
    inputPayload: { optimization: { mode: "comfort_ergonomics", selection_criteria: [
      { field: "catalog_facts", operator: "prefer_match", value: "comfort ergonomic", weight: 10 },
    ] } },
    icon: Heart,
  },
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
