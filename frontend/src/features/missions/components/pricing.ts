import type { Attachment, MissionData } from "./types";

export type RecommendationPriceSummary = {
  kind: "range" | "total";
  minimum: number;
  maximum: number;
  value: number;
  label: string;
};

const money = (value: number) => value.toLocaleString("en-MY", {
  maximumFractionDigits: 0,
});

export function recommendationPriceSummary(
  items: Attachment[],
  recommendationMode: MissionData["recommendation_mode"],
): RecommendationPriceSummary | null {
  const prices = items
    .map((item) => Number(item.price))
    .filter((price) => Number.isFinite(price) && price >= 0);
  if (!prices.length) return null;

  if (recommendationMode === "single" && prices.length > 1) {
    const minimum = Math.min(...prices);
    const maximum = Math.max(...prices);
    return {
      kind: "range",
      minimum,
      maximum,
      value: maximum,
      label: minimum === maximum
        ? `RM ${money(minimum)}`
        : `RM ${money(minimum)} – RM ${money(maximum)}`,
    };
  }

  const total = prices.reduce((sum, price) => sum + price, 0);
  return {
    kind: "total",
    minimum: total,
    maximum: total,
    value: total,
    label: `RM ${money(total)}`,
  };
}
