import { BriefcaseBusiness, CarFront, Gamepad2, House, Plane, Shirt } from "lucide-react";
import styles from "./mission-workspace.module.css";

const cards = [
  { label: "Build my setup", prompt: "Build me a focused WFH setup under RM2,000", icon: BriefcaseBusiness },
  { label: "Fill my room", prompt: "Help me fill and style my room", icon: House },
  { label: "Complete my look", prompt: "Complete my look for a smart casual event", icon: Shirt },
  { label: "Care for my car", prompt: "Build a practical car care kit", icon: CarFront },
  { label: "Prepare my trip", prompt: "Build a weekend travel kit", icon: Plane },
  { label: "Game better", prompt: "Build a balanced gaming setup under RM4,000", icon: Gamepad2 },
];

export default function MissionCards({ onPick }: { onPick: (prompt: string) => void }) {
  return <section className={styles.launcher} aria-labelledby="mission-launcher-title"><div className={styles.sectionIntro}><span>01 · START A MISSION</span><h2 id="mission-launcher-title">Choose a direction, then make it yours.</h2></div><div className={styles.missionCards}>{cards.map(({ label, prompt, icon: Icon }) => <button type="button" key={label} onClick={() => onPick(prompt)}><span><Icon size={20} /></span><strong>{label}</strong><small>{prompt.replace(/^Build me |^Help me /, "")}</small></button>)}</div></section>;
}
