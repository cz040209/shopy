"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { type FormEvent, useEffect, useRef, useState } from "react";
import { ArrowRight, CarFront, ChefHat, Gamepad2, HeartPulse, LoaderCircle, Mic, Paintbrush, Shirt, Square, BriefcaseBusiness, House, Plane } from "lucide-react";
import styles from "./home.module.css";
import heroTheme from "./home-hero-theme.module.css";
import AIShoppingCamera, { type VisionAnalysisResult } from "@/features/vision/components/AIShoppingCamera";
import { API_URL } from "@/lib/api";

const missions = [
  { title: "Build my setup", description: "Complete gaming or desk setups within a budget.", prompt: "Build me a gaming setup under RM4,000.", icon: Gamepad2, tone: "violet" },
  { title: "Fill my room", description: "Show your space and discover what completes it.", prompt: "Help me fill and style my room.", icon: House, tone: "cyan" },
  { title: "Complete my look", description: "Create outfits around your style, event, and wardrobe.", prompt: "Complete my look for a smart casual event.", icon: Shirt, tone: "pink" },
  { title: "Care for my car", description: "Build a practical kit for your car and routine.", prompt: "Build a car care kit for a weekly wash.", icon: CarFront, tone: "orange" },
  { title: "Work smarter", description: "Shape a more focused and comfortable workspace.", prompt: "Build me a comfortable WFH setup under RM2,000.", icon: BriefcaseBusiness, tone: "blue" },
  { title: "Prepare my trip", description: "Pack the essentials for your next journey.", prompt: "Build me a travel kit for a weekend trip.", icon: Plane, tone: "green" },
];

const popular = [[Gamepad2, "Gaming setup", "Build a setup"], [BriefcaseBusiness, "Work setup", "Build a WFH setup"], [House, "Fill my room", "Fill my room"], [Shirt, "Complete my look", "Complete my outfit"], [Plane, "Travel kit", "Build a travel kit"], [CarFront, "Car care", "Build a car care kit"], [HeartPulse, "Skincare", "Build a skincare routine"], [ChefHat, "Cooking setup", "Build a cooking setup"]] as const;

export default function Home() {
  const router = useRouter();
  const [mission, setMission] = useState("Build me a comfortable WFH setup under RM2,000");
  const [voiceState, setVoiceState] = useState<"idle" | "recording" | "transcribing">("idle");
  const [voiceMessage, setVoiceMessage] = useState("");
  const [launchingMission, setLaunchingMission] = useState(false);
  const missionInputRef = useRef<HTMLInputElement>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const beginMission = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const brief = mission.trim();
    if (!brief || launchingMission) return;
    setLaunchingMission(true);
    const launchId = crypto.randomUUID();
    router.push(`/build?mission=${encodeURIComponent(brief)}&autorun=${encodeURIComponent(launchId)}`);
  };

  const openVisionRecommendation = (analysis: string, attachments: VisionAnalysisResult["attachments"], result: VisionAnalysisResult) => {
    const goal = typeof result.mission.goal === "string" && result.mission.goal.trim()
      ? result.mission.goal.trim()
      : result.mode === "complete_look" ? "Complete my look from this photo" : result.mode === "shop_room" ? "Shop this room from this photo" : "Find products from this photo";
    try {
      window.sessionStorage.setItem("shopy:mission-workspace:v2", JSON.stringify({
        version: 2,
        routeMission: goal,
        request: goal,
        analysis,
        mission: result.mission,
        items: attachments,
        workspace: result.workspace,
        history: [],
      }));
    } catch {
      // The destination can still render the URL brief if storage is blocked.
    }
    router.push(`/build?mission=${encodeURIComponent(goal)}`);
  };

  const stopStream = () => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
  };

  useEffect(() => () => {
    if (recorderRef.current?.state === "recording") recorderRef.current.stop();
    stopStream();
  }, []);

  const transcribeRecording = async (recording: Blob) => {
    setVoiceState("transcribing");
    setVoiceMessage("Transcribing your mission…");
    const formData = new FormData();
    formData.append("audio", recording, recording.type.includes("mp4") ? "mission-voice.mp4" : "mission-voice.webm");
    formData.append("language", "en");

    try {
      const response = await fetch(`${API_URL}/api/v1/transcribe`, { method: "POST", body: formData });
      const data = await response.json() as { transcript?: string; detail?: string };
      if (!response.ok || !data.transcript) throw new Error(data.detail ?? "No speech was detected.");
      setMission(data.transcript.trim());
      setVoiceMessage("Transcript added — you can edit it before building.");
      window.requestAnimationFrame(() => missionInputRef.current?.focus());
    } catch (error) {
      setVoiceMessage(error instanceof Error ? error.message : "We couldn’t transcribe that recording. Please try again.");
    } finally {
      setVoiceState("idle");
    }
  };

  const startVoiceInput = async () => {
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setVoiceMessage("Voice input is not supported in this browser.");
      return;
    }
    try {
      setVoiceMessage("Listening… click the microphone again when you’re finished.");
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mimeType = ["audio/webm;codecs=opus", "audio/mp4", "audio/webm"].find((type) => MediaRecorder.isTypeSupported(type));
      const recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
      const chunks: BlobPart[] = [];
      streamRef.current = stream;
      recorderRef.current = recorder;
      recorder.ondataavailable = (event) => { if (event.data.size > 0) chunks.push(event.data); };
      recorder.onstop = () => {
        stopStream();
        const recording = new Blob(chunks, { type: recorder.mimeType || "audio/webm" });
        if (recording.size) void transcribeRecording(recording);
        else {
          setVoiceState("idle");
          setVoiceMessage("No audio was captured. Please try again.");
        }
      };
      recorder.start();
      setVoiceState("recording");
    } catch {
      stopStream();
      setVoiceState("idle");
      setVoiceMessage("Microphone access was not allowed. Enable it and try again.");
    }
  };

  const toggleVoiceInput = () => {
    if (voiceState === "recording") {
      recorderRef.current?.stop();
      return;
    }
    if (voiceState === "idle") void startVoiceInput();
  };

  return <main className={styles.home}>
    <section className={`${styles.hero} ${heroTheme.hero}`}>
      <div className={`${styles.orbOne} ${heroTheme.orbOne}`} /><div className={`${styles.orbTwo} ${heroTheme.orbTwo}`} />
      <span className={styles.kicker}>AI commerce, built around your goal</span>
      <h1>What can we <em>build</em> for you?</h1>
      <p className={styles.intro}>Skip the product hunt. Tell Shopy what you are trying to achieve, then let the right products come together.</p>
      <form className={styles.missionBar} onSubmit={beginMission}>
        <label className="sr-only" htmlFor="mission">What do you want to achieve today?</label>
        <input ref={missionInputRef} id="mission" value={mission} onChange={(event) => setMission(event.target.value)} placeholder="What do you want to achieve today?" />
        <button type="button" className={`${styles.inputAction} ${voiceState === "recording" ? "home-voice-recording" : ""}`} onClick={toggleVoiceInput} disabled={voiceState === "transcribing"} aria-label={voiceState === "recording" ? "Stop recording and transcribe" : "Record a mission by voice"} aria-pressed={voiceState === "recording"}>
          {voiceState === "transcribing" ? <LoaderCircle className="home-voice-spinner" size={19} /> : voiceState === "recording" ? <Square size={16} fill="currentColor" /> : <Mic size={19} />}
        </button>
        <AIShoppingCamera compact showResult={false} onAnalysisComplete={openVisionRecommendation} />
        <button className={styles.buildButton} type="submit" disabled={launchingMission}>
          {launchingMission ? "Opening workspace…" : "Build for me"} <ArrowRight size={17} />
        </button>
      </form>
      {voiceMessage && <p className="home-voice-hint" role="status">{voiceMessage}</p>}
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
  </main>;
}
