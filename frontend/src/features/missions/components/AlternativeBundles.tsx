import { ArrowRightLeft } from "lucide-react";
import { Attachment } from "./types";
import styles from "./mission-studio.module.css";

export default function AlternativeBundles({ items, onExplore }: { items: Attachment[]; onExplore: (prompt: string) => void }) {
  if (items.length < 2) return null;
  const options = [{ title: "Best value edit", copy: "Keeps the core outcome with more room in the budget.", prompt: "Show a best value alternative" }, { title: "Elevated edit", copy: "A stronger finish with a little more emphasis on quality.", prompt: "Show a more premium alternative" }];
  return <section className={styles.alternatives}><div className={styles.sectionIntro}><span>ALTERNATIVE BUNDLES</span><h2>Try a different trade-off.</h2></div><div>{options.map((option) => <article key={option.title}><strong>{option.title}</strong><p>{option.copy}</p><button type="button" onClick={() => onExplore(option.prompt)}>Explore <ArrowRightLeft size={13} /></button></article>)}</div></section>;
}
