"use client";

import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { ArrowLeft, CircleCheck, RefreshCw, WandSparkles } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { API_URL, apiFetch } from "@/lib/api";
import AIProgressPanel from "./AIProgressPanel";
import AlternativeBundles from "./AlternativeBundles";
import BundleBoard from "./BundleBoard";
import MissionHistory from "./MissionHistory";
import MissionInputPanel from "./MissionInputPanel";
import OptimizationActions from "./OptimizationActions";
import { Attachment, BundleWorkspace, MissionData, MissionHistoryItem } from "./types";
import styles from "./mission-studio.module.css";

const emptyMission: MissionData = { preferences: [], owned_items: [], priorities: [] };
const progressStepCount = 6;
const stageDurationMs = 1100;

function draftMission(text: string): MissionData {
  const budget = text.match(/(?:under|below|budget(?:\s+of)?|within)\s*(?:rm)?\s*([\d,]+)/i)?.[1];
  const owned = text.match(/(?:already own|i have|with my)\s+([^.,]+)/i)?.[1]
    ?.split(/,| and /i)
    .map((item) => item.trim())
    .filter(Boolean) ?? [];
  const preferenceTerms = ["minimal", "comfortable", "wireless", "warm", "ergonomic", "best value", "smart casual"]
    .filter((term) => text.toLowerCase().includes(term));

  return {
    budget: budget ? Number(budget.replaceAll(",", "")) : null,
    preferences: preferenceTerms,
    owned_items: owned,
  };
}

export default function MissionWorkspace() {
  const search = useSearchParams();
  const reduceMotion = useReducedMotion();
  const initialRequest = search.get("mission") ?? "";
  const [request, setRequest] = useState(initialRequest);
  const [mission, setMission] = useState<MissionData>(() => draftMission(initialRequest));
  const [busy, setBusy] = useState(false);
  const [progressStep, setProgressStep] = useState(0);
  const [analysis, setAnalysis] = useState("");
  const [items, setItems] = useState<Attachment[]>([]);
  const [bundleWorkspace, setBundleWorkspace] = useState<BundleWorkspace>({});
  const [error, setError] = useState("");
  const [adding, setAdding] = useState(false);
  const [history, setHistory] = useState<MissionHistoryItem[]>([]);
  const complete = Boolean(analysis);
  const total = useMemo(() => items.reduce((sum, item) => sum + Number(item.price), 0), [items]);

  useEffect(() => {
    if (!busy) return;
    const timer = window.setInterval(() => {
      setProgressStep((current) => Math.min(current + 1, progressStepCount - 1));
    }, stageDurationMs);
    return () => window.clearInterval(timer);
  }, [busy]);

  const runMission = async (nextRequest = request) => {
    if (!nextRequest.trim()) return;
    const startedAt = performance.now();
    setBusy(true);
    setProgressStep(0);
    setError("");
    setAnalysis("");
    setItems([]);
    setBundleWorkspace({});

    try {
      const response = await fetch(`${API_URL}/api/chat`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: [{ role: "user", content: nextRequest.trim() }] }),
      });
      const data = await response.json() as {
        reply?: string;
        detail?: string;
        attachments?: Attachment[];
        mission?: MissionData;
        workspace?: BundleWorkspace;
      };

      if (!response.ok || !data.reply) {
        throw new Error(data.detail ?? "We could not complete that mission right now.");
      }

      const nextItems = data.attachments ?? [];
      const sequenceDuration = stageDurationMs * progressStepCount;
      const remainingSequenceTime = Math.max(0, sequenceDuration - (performance.now() - startedAt));
      if (remainingSequenceTime > 0) {
        await new Promise<void>((resolve) => window.setTimeout(resolve, remainingSequenceTime));
      }

      setProgressStep(progressStepCount);
      setAnalysis(data.reply);
      setItems(nextItems);
      setBundleWorkspace(data.workspace ?? {});
      setMission({ ...emptyMission, ...data.mission });
      setHistory((previous) => [{
        id: crypto.randomUUID(),
        label: data.mission?.goal || nextRequest,
        total: nextItems.reduce((sum, item) => sum + Number(item.price), 0),
        at: "Just now",
      }, ...previous].slice(0, 5));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "We could not complete that mission right now.");
    } finally {
      setBusy(false);
    }
  };

  const removeOwned = (item: string) => {
    setMission((current) => ({
      ...current,
      owned_items: (current.owned_items ?? []).filter((owned) => owned !== item),
    }));
  };

  const refine = (instruction: string) => {
    const next = `${request.trim()}. ${instruction}.`;
    setRequest(next);
    void runMission(next);
  };

  const addBundle = async () => {
    if (!items.length) return;
    setAdding(true);
    try {
      await Promise.all(items.map((item) => apiFetch("/api/v1/cart/items", {
        method: "POST",
        body: JSON.stringify({ product_id: item.product_id, quantity: 1 }),
      })));
    } finally {
      setAdding(false);
    }
  };

  const enter = reduceMotion ? {} : { opacity: 0, y: 22 };

  return (
    <main className={styles.page}>
      <motion.nav className={styles.topbar} initial={enter} animate={{ opacity: 1, y: 0 }}>
        <Link className={styles.back} href="/">
          <ArrowLeft size={18} /> All missions
        </Link>
        <span className={styles.liveStatus}><i /> AI mission studio</span>
      </motion.nav>

      <motion.header
        className={styles.hero}
        initial={enter}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.55, ease: [0.22, 1, 0.36, 1] }}
      >
        <motion.div
          className={styles.orb}
          aria-hidden="true"
          animate={reduceMotion ? undefined : { x: [0, 28, 0], y: [0, -18, 0], scale: [1, 1.08, 1] }}
          transition={{ duration: 9, repeat: Infinity, ease: "easeInOut" }}
        />
        <div className={styles.heroCopy}>
          <span><WandSparkles size={16} /> ACTIVE MISSION</span>
          <h1>One brief.<br /><em>A complete answer.</em></h1>
          <p>Tell Shopy the outcome. The AI turns your words into a structured brief, researches the catalog, and builds a visual bundle around you.</p>
          <div className={styles.heroSignals}>
            <span><CircleCheck size={16} /> Preferences understood</span>
            <span><CircleCheck size={16} /> Compatibility checked</span>
            <span><CircleCheck size={16} /> Budget optimized</span>
          </div>
        </div>
        <div className={styles.briefPreview}>
          <div className={styles.previewTopline}>
            <span>YOUR BRIEF</span>
            <b>{busy ? "AI WORKING" : complete ? "READY" : "DRAFT"}</b>
          </div>
          <p>{request || "Describe what you want to make happen."}</p>
          <div className={styles.previewMeta}>
            <span>Budget <strong>{mission.budget ? `RM ${Number(mission.budget).toLocaleString()}` : "Flexible"}</strong></span>
            <span>Owned <strong>{mission.owned_items?.length ?? 0} items</strong></span>
          </div>
        </div>
      </motion.header>

      <motion.section
        className={styles.studioGrid}
        initial={enter}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: reduceMotion ? 0 : 0.14, duration: 0.55, ease: [0.22, 1, 0.36, 1] }}
      >
        <MissionInputPanel
          request={request}
          mission={mission}
          busy={busy}
          onRequestChange={(value) => {
            setRequest(value);
            setMission(draftMission(value));
          }}
          onLaunch={() => void runMission()}
          onRemoveOwned={removeOwned}
        />
        <AIProgressPanel busy={busy} complete={complete} activeStep={progressStep} />
      </motion.section>

      <AnimatePresence mode="wait">
        {error && (
          <motion.section className={styles.error} key="error" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }}>
            <div><strong>Mission paused.</strong><p>{error}</p></div>
            <button type="button" onClick={() => void runMission()}><RefreshCw size={16} /> Try again</button>
          </motion.section>
        )}

        {complete && (
          <motion.section
            className={styles.results}
            key="results"
            initial={{ opacity: 0, y: 26, scale: 0.99 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{ duration: 0.55, ease: [0.22, 1, 0.36, 1] }}
          >
            <div className={styles.resultHeading}>
              <span>MISSION COMPLETE</span>
              <h2>Your bundle, ready to explore.</h2>
              {items.length > 0 && <strong>RM {total.toLocaleString("en-MY", { maximumFractionDigits: 0 })}</strong>}
            </div>
            <OptimizationActions disabled={busy} onPick={refine} />
            {items.length ? (
              <BundleBoard items={items} mission={mission} workspace={bundleWorkspace} adding={adding} onAdd={() => void addBundle()} />
            ) : (
              <section className={styles.insight}><span>MISSION INSIGHT</span><p>{analysis}</p></section>
            )}
            <AlternativeBundles items={items} onExplore={refine} />
          </motion.section>
        )}
      </AnimatePresence>

      <MissionHistory entries={history} onRestore={(label) => { setRequest(label); setMission(draftMission(label)); }} />
    </main>
  );
}
