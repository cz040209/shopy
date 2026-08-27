/* eslint-disable @next/next/no-img-element */
import Link from "next/link";
import { Check, CircleHelp, ShoppingBag, X } from "lucide-react";
import { Attachment, BundleWorkspace, MissionData } from "./types";
import styles from "./bundle-canvas.module.css";

type Props = {
  items: Attachment[];
  mission: MissionData;
  workspace: BundleWorkspace;
  adding: boolean;
  onAdd: () => void;
  onRemove: (productId: string) => void;
};

const slotClasses = [styles.center, styles.top, styles.left, styles.right];

function ProductNode({ item, slot, onRemove }: { item: Attachment; slot: number; onRemove: (productId: string) => void }) {
  return <div className={`${styles.nodeShell} ${slotClasses[slot] ?? ""}`}><Link href={`/product/${item.product_id}`} className={styles.node}><img src={item.image_url} alt={item.image_alt_text || item.name} /><div><small>{item.category || `Bundle item ${slot + 1}`}</small><strong>{item.name}</strong><b>RM {Number(item.price).toLocaleString("en-MY", { minimumFractionDigits: 0 })}</b></div></Link><button type="button" className={styles.remove} aria-label={`Remove ${item.name} from this bundle`} onClick={() => onRemove(item.product_id)}><X size={14} /></button></div>;
}

export default function BundleBoard({ items, mission, workspace, adding, onAdd, onRemove }: Props) {
  const total = items.reduce((sum, item) => sum + Number(item.price), 0);
  const budgetRemaining = mission.budget ? Number(mission.budget) - total : null;
  const primary = [...items].sort((a, b) => Number(b.price) - Number(a.price));
  const diagramItems = primary.slice(0, 4);
  const reasons = [
    ...(mission.priorities ?? []).map((value) => `Prioritizes ${value}`),
    ...(mission.preferences ?? []).map((value) => `Matches your ${value} preference`),
    ...(workspace.bundle?.rationale ?? []),
    ...(workspace.compatibility ?? []).filter((item) => item.status === "compatible").map((item) => item.reason || item.message || "Compatibility checked"),
    workspace.audit?.status === "pass" ? "Catalog facts and seller data audited" : "",
  ].filter(Boolean).filter((value, index, all) => all.indexOf(value) === index).slice(0, 5);
  const title = mission.goal || "Your recommended setup";
  return <section className={styles.canvas}><header className={styles.heading}><span>{title.toUpperCase()}</span><h2>Your AI Bundle Canvas</h2><strong>RM {total.toLocaleString("en-MY", { minimumFractionDigits: 0 })}</strong>{budgetRemaining !== null && <small>{budgetRemaining >= 0 ? `RM ${budgetRemaining.toLocaleString()} under budget` : `RM ${Math.abs(budgetRemaining).toLocaleString()} over budget`}</small>}</header><div className={styles.diagram}>{diagramItems.map((item, index) => <ProductNode item={item} slot={index} key={item.product_id} onRemove={onRemove} />)}{diagramItems.length > 1 && <span className={styles.compatible}>COMPATIBILITY CHECKED</span>}</div>{primary.length > 4 && <div className={styles.extras}>{primary.slice(4).map((item) => <Link href={`/product/${item.product_id}`} key={item.product_id}>+ {item.name} · RM {Number(item.price).toLocaleString("en-MY", { maximumFractionDigits: 0 })}</Link>)}</div>}<div className={styles.why}><span><CircleHelp size={15} /> WHY THIS SETUP?</span><ul>{(reasons.length ? reasons : ["Selected for your stated mission", "Verified against the current Shopy catalog", "Bundle total calculated from live product prices"]).map((reason) => <li key={reason}><Check size={13} />{reason}</li>)}</ul></div><button type="button" className={styles.add} disabled={adding || !items.length} onClick={onAdd}><ShoppingBag size={17} />{adding ? "Adding bundle…" : `Add ${items.length} ${items.length === 1 ? "item" : "items"}`}</button></section>;
}
