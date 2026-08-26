"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";
import { ArrowRight, CarFront, ChefHat, Gamepad2, Mic, Paintbrush, Shirt, Sparkles, Wrench, BriefcaseBusiness, House, Plane } from "lucide-react";
import styles from "./home.module.css";
import AIShoppingCamera from "@/features/vision/components/AIShoppingCamera";

const missions = [
  { title: "Build my setup", description: "Complete gaming or desk setups within a budget.", prompt: "Build me a gaming setup under RM4,000.", icon: Gamepad2, tone: "violet" },
  { title: "Fill my room", description: "Show your space and discover what completes it.", prompt: "Help me fill and style my room.", icon: House, tone: "cyan" },
  { title: "Complete my look", description: "Create outfits around your style, event, and wardrobe.", prompt: "Complete my look for a smart casual event.", icon: Shirt, tone: "pink" },
  { title: "Care for my car", description: "Build a practical kit for your car and routine.", prompt: "Build a car care kit for a weekly wash.", icon: CarFront, tone: "orange" },
  { title: "Work smarter", description: "Shape a more focused and comfortable workspace.", prompt: "Build me a comfortable WFH setup under RM2,000.", icon: BriefcaseBusiness, tone: "blue" },
  { title: "Prepare my trip", description: "Pack the essentials for your next journey.", prompt: "Build me a travel kit for a weekend trip.", icon: Plane, tone: "green" },
];

const popular = [[Gamepad2, "Gaming setup", "Build a setup"], [BriefcaseBusiness, "Work setup", "Build a WFH setup"], [House, "Fill my room", "Fill my room"], [Shirt, "Complete my look", "Complete my outfit"], [Plane, "Travel kit", "Build a travel kit"], [CarFront, "Car care", "Build a car care kit"], [Sparkles, "Skincare", "Build a skincare routine"], [ChefHat, "Cooking setup", "Build a cooking setup"]] as const;

export default function Home() {
  const router = useRouter();
  const [mission, setMission] = useState("Build me a comfortable WFH setup under RM2,000");
  const beginMission = (event: FormEvent<HTMLFormElement>) => { event.preventDefault(); if (mission.trim()) router.push(`/build?mission=${encodeURIComponent(mission.trim())}`); };

  return <main className={styles.home}>
    <section className={styles.hero}>
      <div className={styles.orbOne} /><div className={styles.orbTwo} />
      <span className={styles.kicker}><Sparkles size={14} /> AI commerce, built around your goal</span>
      <h1>What can we <em>build</em> for you?</h1>
      <p className={styles.intro}>Skip the product hunt. Tell Shopy what you are trying to achieve, then let the right products come together.</p>
      <form className={styles.missionBar} onSubmit={beginMission}>
        <Sparkles className={styles.missionSparkle} size={22} aria-hidden="true" />
        <label className="sr-only" htmlFor="mission">What do you want to achieve today?</label>
        <input id="mission" value={mission} onChange={(event) => setMission(event.target.value)} placeholder="What do you want to achieve today?" />
        <button type="button" className={styles.inputAction} onClick={() => router.push(`/build?mission=${encodeURIComponent(mission)}&input=voice`)} aria-label="Tell Shopy by voice"><Mic size={19} /></button>
        <AIShoppingCamera compact />
        <button className={styles.buildButton} type="submit">Build for me <ArrowRight size={17} /></button>
      </form>
      <div className={styles.quickActions}><span>Try a mission</span>{popular.slice(0, 4).map(([Icon, label, prompt]) => <Link key={label} href={`/build?mission=${encodeURIComponent(prompt)}`}><Icon size={15} />{label}</Link>)}</div>
    </section>
    <section className={styles.missions} aria-labelledby="mission-heading">
      <div className={styles.sectionHeading}><div><span>Popular missions</span><h2 id="mission-heading">Start with what you want to make happen.</h2></div><Link href="/shop">Browse products instead <ArrowRight size={16} /></Link></div>
      <div className={styles.missionGrid}>{missions.map(({ title, description, prompt, icon: Icon, tone }) => <Link className={`${styles.missionCard} ${styles[tone]}`} href={`/build?mission=${encodeURIComponent(prompt)}`} key={title}><span className={styles.cardIcon}><Icon size={27} /></span><div><h3>{title}</h3><p>{description}</p></div><ArrowRight className={styles.cardArrow} size={18} /></Link>)}</div>
    </section>
    <section className={styles.feature}>
      <div className={styles.featureCopy}><span className={styles.kicker}><Paintbrush size={14} /> Your goal, not a keyword</span><h2>From “I need a desk” to a workspace that works.</h2><p>Set a budget, say what matters, add what you already own, or show us the space. Shopy checks the details and builds a recommendation you can understand.</p><Link href="/build?mission=Build%20me%20a%20comfortable%20WFH%20setup%20under%20RM2%2C000" className={styles.featureLink}>Try Build it for me <ArrowRight size={17} /></Link></div>
      <div className={styles.preview} aria-label="Example agent activity"><div className={styles.previewTop}><span>BUILDING YOUR WORKSPACE</span><span>LIVE PLAN</span></div>{["Understood your requirements", "Found products that fit your budget", "Checked compatibility and practical details", "Optimizing your bundle"].map((step, index) => <div className={styles.progressStep} key={step}><span className={index < 3 ? styles.done : styles.active}>{index < 3 ? "✓" : ""}</span>{step}</div>)}<div className={styles.previewTotal}><span>Estimated bundle</span><strong>RM 1,846</strong><small>RM 154 under budget</small></div></div>
    </section>
    <section className={styles.bottomCta}><Wrench size={23} /><div><h2>Got a problem to solve?</h2><p>Describe the situation and we will turn it into a practical next step.</p></div><Link href="/build?mission=Help%20me%20solve%20a%20shopping%20problem">Fix my problem <ArrowRight size={17} /></Link></section>
  </main>;
}
