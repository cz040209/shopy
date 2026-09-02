"use client";

import Link from "next/link";
import { Check, CircleAlert, CircleHelp, Package, ShieldCheck, ShoppingBag, ShoppingCart, X } from "lucide-react";
import ProductImage from "@/features/products/components/ProductImage";
import { recommendationPriceSummary } from "./pricing";
import { Attachment, BundleWorkspace, MissionData } from "./types";
import styles from "./bundle-canvas.module.css";

type Props = {
  items: Attachment[];
  mission: MissionData;
  workspace: BundleWorkspace;
  adding: boolean;
  addingProductId: string | null;
  onAdd: () => void;
  onAddItem: (productId: string) => void;
  onRemove: (productId: string) => void;
};

const money = (value: number) => value.toLocaleString("en-MY", { maximumFractionDigits: 0 });

function readableReason(value: string) {
  const cleaned = value.replaceAll("_", " ").replace(/\bdeterministically\b/gi, "").replace(/\s+/g, " ").replace(/\s+([.,])/g, "$1").trim();
  return cleaned ? cleaned[0].toUpperCase() + cleaned.slice(1) : "";
}

function ProductNode({ item, index, adding, showAdd, onAdd, onRemove }: { item: Attachment; index: number; adding: boolean; showAdd: boolean; onAdd: (productId: string) => void; onRemove: (productId: string) => void }) {
  const initials = item.name.split(/\s+/).filter(Boolean).slice(0, 2).map((word) => word[0]).join("").toUpperCase();
  return <article className={`${styles.nodeShell} ${styles[`nodeTone${index % 5}`]}`}><Link href={`/product/${item.product_id}`} className={styles.node} aria-label={`View ${item.name}`}><div className={styles.media}><ProductImage src={item.image_url} alt={item.image_alt_text || item.name} fill sizes="(max-width: 650px) 80px, 104px" className={styles.productImage} fallback={<span className={styles.imageFallback} aria-hidden="true"><Package size={24} /><b>{initials}</b></span>} /><span className={styles.sequence}>{String(index + 1).padStart(2, "0")}</span></div><div className={styles.nodeCopy}><small>{item.category || "Recommended item"}</small><strong title={item.name}>{item.name}</strong>{item.brand && <span className={styles.brand}>{item.brand}</span>}<b>RM {money(Number(item.price))}</b></div></Link><button type="button" className={styles.remove} aria-label={`Remove ${item.name} from this recommendation`} onClick={() => onRemove(item.product_id)}><X size={15} /></button>{showAdd && <button type="button" className={styles.optionAdd} disabled={adding} onClick={() => onAdd(item.product_id)}><ShoppingCart size={15} />{adding ? "Adding…" : "Add to cart"}</button>}</article>;
}

export default function BundleBoard({ items, mission, workspace, adding, addingProductId, onAdd, onAddItem, onRemove }: Props) {
  const isSingleRecommendation = mission.recommendation_mode === "single";
  const isComparison = isSingleRecommendation && items.length > 1;
  const total = items.reduce((sum, item) => sum + Number(item.price), 0);
  const priceSummary = recommendationPriceSummary(items, mission.recommendation_mode);
  const hasBudget = mission.budget !== null && mission.budget !== undefined;
  const budget = hasBudget ? Number(mission.budget) : null;
  const budgetRemaining = budget === null ? null : budget - total;
  const budgetPercent = budget && budget > 0 ? Math.min((total / budget) * 100, 100) : 0;
  const overBudget = budgetRemaining !== null && budgetRemaining < 0;
  const products = [...items].sort((a, b) => Number(b.price) - Number(a.price));
  const coverage = workspace.bundle?.required_category_coverage;
  const covered = coverage?.covered ?? [];
  const missing = coverage?.missing ?? [];
  const plannedCount = new Set([...covered, ...missing]).size;
  const compatibilityVerified = (workspace.compatibility ?? []).some((item) => item.status === "compatible");
  const reasons = [...(mission.priorities ?? []).map((value) => `Prioritizes ${value}`), ...(mission.preferences ?? []).map((value) => `Matches your ${value} preference`), ...(workspace.bundle?.rationale ?? []), ...(workspace.compatibility ?? []).filter((item) => item.status === "compatible").map((item) => item.reason || item.message || "Compatibility checked"), workspace.audit?.status === "pass" ? "Catalog facts and seller data audited" : ""].map(readableReason).filter(Boolean).filter((value, index, all) => all.indexOf(value) === index).slice(0, 6);
  const title = mission.goal || "Your recommended setup";
  return <section className={styles.canvas}>
    <header className={styles.heading}><span>{title.toUpperCase()}</span><h2>{isComparison ? "Verified product shortlist" : isSingleRecommendation ? "Verified product recommendation" : "Recommended mission bundle"}</h2><p>{isComparison ? `${items.length} verified options to compare` : isSingleRecommendation ? "1 verified option selected for this mission" : `${items.length} coordinated ${items.length === 1 ? "item" : "items"} selected for this mission`}</p>{priceSummary && <strong>{priceSummary.label}</strong>}</header>
    {!isSingleRecommendation && hasBudget && budget !== null && <div className={`${styles.budgetCard} ${overBudget ? styles.budgetOver : styles.budgetWithin}`}><div><span>Bundle budget</span><b>RM {money(total)} <small>of RM {money(budget)}</small></b></div><strong>{overBudget ? `RM ${money(Math.abs(budgetRemaining ?? 0))} over` : `RM ${money(budgetRemaining ?? 0)} remaining`}</strong><div className={styles.budgetTrack} aria-label={`${Math.round(total / Math.max(budget, 1) * 100)} percent of budget used`}><i style={{ width: `${budgetPercent}%` }} /></div></div>}
    <div className={`${styles.diagram} ${isSingleRecommendation ? styles.comparison : ""}`}>{!isSingleRecommendation && <div className={styles.bundleHub}><span><ShieldCheck size={18} /></span><div><small>RECOMMENDATION MAP</small><strong>{compatibilityVerified ? "Compatibility verified" : "Catalog-verified selection"}</strong></div><b>{items.length} {items.length === 1 ? "PICK" : "PICKS"}</b></div>}<div className={styles.productGrid}>{products.map((item, index) => <ProductNode item={item} index={index} key={item.product_id} adding={addingProductId === item.product_id} showAdd={isSingleRecommendation} onAdd={onAddItem} onRemove={onRemove} />)}</div></div>
    {!isSingleRecommendation && plannedCount > 0 && <div className={styles.coverage}><div className={styles.coverageHeading}><span>PLAN COVERAGE</span><strong>{covered.length} of {plannedCount} roles covered</strong></div><div className={styles.coverageChips}>{covered.map((role, index) => <span className={`${styles.coveredChip} ${styles[`coverageTone${index % 5}`]}`} key={`covered-${role}`}><Check size={13} />{role}</span>)}{missing.map((role) => <span className={styles.missingChip} key={`missing-${role}`}><CircleAlert size={13} />Not found: {role}</span>)}</div>{missing.length > 0 && <p>The available recommendations remain usable, but these requested roles could not be filled from verified catalog matches.</p>}</div>}
    <div className={styles.why}><span><CircleHelp size={15} /> {isComparison ? "WHY THESE OPTIONS?" : isSingleRecommendation ? "WHY THIS OPTION?" : "WHY THIS SETUP?"}</span><ul>{(reasons.length ? reasons : ["Selected for your stated mission", "Verified against the current Shopy catalog", isSingleRecommendation ? "Each option is evaluated independently" : "Bundle total calculated from current product prices"]).map((reason, index) => <li className={styles[`reasonTone${index % 5}`]} key={reason}><Check size={14} />{reason}</li>)}</ul></div>
    {!isSingleRecommendation && <button type="button" className={styles.add} disabled={adding || !items.length} onClick={onAdd}><ShoppingBag size={17} />{adding ? "Adding bundle…" : `Add all ${items.length} ${items.length === 1 ? "item" : "items"}`}</button>}
  </section>;
}
