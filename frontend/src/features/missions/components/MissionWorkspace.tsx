"use client";

import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { ArrowLeft, CircleCheck, RefreshCw, WandSparkles } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { API_URL, apiFetch } from "@/lib/api";
import { useCart } from "@/features/cart/cart-context";
import AIProgressPanel from "./AIProgressPanel";
import AlternativeBundles from "./AlternativeBundles";
import BundleBoard from "./BundleBoard";
import MissionHistory from "./MissionHistory";
import MissionInputPanel from "./MissionInputPanel";
import OptimizationActions from "./OptimizationActions";
import { recommendationPriceSummary } from "./pricing";
import { Attachment, BundleWorkspace, MissionData, MissionHistoryItem } from "./types";
import styles from "./mission-studio.module.css";

const emptyMission: MissionData = { preferences: [], owned_items: [], priorities: [] };
const progressStepCount = 6;
const stageDurationMs = 1800;
const workspaceStorageKey = "shopy:mission-workspace:v2";

type StoredMissionWorkspace = {
  version: 2;
  routeMission: string;
  request: string;
  analysis: string;
  mission: MissionData;
  items: Attachment[];
  workspace: BundleWorkspace;
  history: MissionHistoryItem[];
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function isAttachment(value: unknown): value is Attachment {
  if (!isRecord(value)) return false;
  return typeof value.product_id === "string"
    && typeof value.name === "string"
    && (typeof value.price === "string" || typeof value.price === "number")
    && typeof value.currency === "string"
    && typeof value.image_url === "string";
}

function isHistoryItem(value: unknown): value is MissionHistoryItem {
  return isRecord(value)
    && typeof value.id === "string"
    && typeof value.label === "string"
    && typeof value.price_label === "string"
    && typeof value.at === "string";
}

function readStoredWorkspace(): StoredMissionWorkspace | null {
  try {
    const raw = window.sessionStorage.getItem(workspaceStorageKey);
    if (!raw) return null;
    const value: unknown = JSON.parse(raw);
    if (!isRecord(value)
      || value.version !== 2
      || typeof value.routeMission !== "string"
      || typeof value.request !== "string"
      || typeof value.analysis !== "string"
      || !value.analysis.trim()
      || !isRecord(value.mission)
      || !Array.isArray(value.items)
      || !value.items.every(isAttachment)
      || !isRecord(value.workspace)
      || !Array.isArray(value.history)
      || !value.history.every(isHistoryItem)) {
      return null;
    }
    return value as StoredMissionWorkspace;
  } catch {
    // Storage can be unavailable or contain data from an older app version.
    return null;
  }
}

function draftMission(text: string): MissionData {
  const budget = text.match(/(?:under|below|budget(?:\s+of)?|within)\s*(?:rm)?\s*([\d,]+)/i)?.[1];
  const budgetValue = budget ? Number(budget.replaceAll(",", "")) : null;
  const normalized = text.toLowerCase();
  const owned = text.match(/(?:already own|i have|with my)\s+([^.,]+)/i)?.[1]
    ?.split(/,| and /i)
    .map((item) => item.trim())
    .filter(Boolean) ?? [];
  const preferenceTerms = ["minimal", "comfortable", "wireless", "warm", "ergonomic", "best value", "smart casual", "premium", "budget-friendly", "portable", "quiet", "durable"]
    .filter((term) => normalized.includes(term));
  const categoryMatchers: Array<{ pattern: RegExp; label: string }> = [
    { pattern: /\b(clothes?|outfit|shirt|dress|jacket|fashion)\b/, label: "Clothes" },
    { pattern: /\b(shoes?|sneakers?|boots?)\b/, label: "Shoes" },
    { pattern: /\b(gaming|game|pc|computer)\b/, label: "Gaming setup" },
    { pattern: /\b(work|wfh|desk|office)\b/, label: "Workspace" },
    { pattern: /\b(phone|laptop|tablet|headphones?|keyboard|mouse)\b/, label: "Tech" },
    { pattern: /\b(room|bedroom|living room|furniture|sofa)\b/, label: "Home" },
    { pattern: /\b(car|vehicle|wash)\b/, label: "Car care" },
    { pattern: /\b(travel|trip|holiday|pack)\b/, label: "Travel" },
  ];
  const categories = categoryMatchers.flatMap(({ pattern, label }) => pattern.test(normalized) ? [label] : []);
  const keyRequirements = [...new Set(categories)].map((category) => (
    budgetValue ? `${category} under RM ${budgetValue.toLocaleString("en-MY")}` : category
  ));

  return {
    budget: budgetValue,
    preferences: preferenceTerms,
    key_requirements: keyRequirements,
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
  const [addingProductId, setAddingProductId] = useState<string | null>(null);
  const [history, setHistory] = useState<MissionHistoryItem[]>([]);
  const [feedback, setFeedback] = useState("");
  const [showBundleReady, setShowBundleReady] = useState(false);
  const resultsRef = useRef<HTMLElement>(null);
  const { refreshCart } = useCart();
  const complete = Boolean(analysis);
  const priceSummary = useMemo(
    () => recommendationPriceSummary(items, mission.recommendation_mode),
    [items, mission.recommendation_mode],
  );

  useEffect(() => {
    if (!busy) return;
    const timer = window.setInterval(() => {
      setProgressStep((current) => Math.min(current + 1, progressStepCount - 1));
    }, stageDurationMs);
    return () => window.clearInterval(timer);
  }, [busy]);

  useEffect(() => {
    const stored = readStoredWorkspace();
    // A mission supplied in the URL represents a new brief unless it matches
    // the saved workspace (as it does when returning from a product page).
    if (!stored || stored.routeMission !== initialRequest) return;
    const frame = window.requestAnimationFrame(() => {
      setRequest(stored.request);
      setAnalysis(stored.analysis);
      setMission({ ...emptyMission, ...stored.mission });
      setItems(stored.items);
      setBundleWorkspace(stored.workspace);
      setHistory(stored.history.slice(0, 5));
      setProgressStep(progressStepCount);
    });
    return () => window.cancelAnimationFrame(frame);
  }, [initialRequest]);

  useEffect(() => {
    if (!analysis.trim()) return;
    const snapshot: StoredMissionWorkspace = {
      version: 2,
      routeMission: initialRequest,
      request,
      analysis,
      mission,
      items,
      workspace: bundleWorkspace,
      history: history.slice(0, 5),
    };
    try {
      window.sessionStorage.setItem(workspaceStorageKey, JSON.stringify(snapshot));
    } catch {
      // The recommendation remains usable even when browser storage is blocked.
    }
  }, [analysis, bundleWorkspace, history, initialRequest, items, mission, request]);

  useEffect(() => {
    if (!showBundleReady) return;
    const timer = window.setTimeout(() => setShowBundleReady(false), 6000);
    return () => window.clearTimeout(timer);
  }, [showBundleReady]);

  const revealBundle = () => {
    setShowBundleReady(false);
    resultsRef.current?.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "start" });
  };

  const runMission = async (nextRequest = request) => {
    if (!nextRequest.trim()) return;
    const startedAt = performance.now();
    setBusy(true);
    setProgressStep(0);
    setError("");
    setAnalysis("");
    setItems([]);
    setBundleWorkspace({});
    setShowBundleReady(false);

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
      setShowBundleReady(nextItems.length > 0);
      setHistory((previous) => [{
        id: crypto.randomUUID(),
        label: data.mission?.goal || nextRequest,
        price_label: recommendationPriceSummary(
          nextItems,
          data.mission?.recommendation_mode,
        )?.label ?? "No priced options",
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
    const next = instruction.trim();
    if (!next) return;
    setFeedback("");
    // Send feedback as a new turn. The server keeps the active brief, prior
    // selections, and earlier feedback in expiring shopping-session memory.
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
      await refreshCart();
    } finally {
      setAdding(false);
    }
  };

  const addRecommendation = async (productId: string) => {
    setAddingProductId(productId);
    setError("");
    try {
      await apiFetch("/api/v1/cart/items", {
        method: "POST",
        body: JSON.stringify({ product_id: productId, quantity: 1 }),
      });
      await refreshCart();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not add this item to your cart.");
    } finally {
      setAddingProductId(null);
    }
  };

  const removeBundleItem = (productId: string) => {
    setItems((current) => current.filter((item) => item.product_id !== productId));
  };

  const enter = reduceMotion ? {} : { opacity: 0, y: 22 };

  return (
    <main className={styles.page}>
      <motion.nav className={styles.topbar} initial={enter} animate={{ opacity: 1, y: 0 }}>
        <Link className={styles.back} href="/">
          <ArrowLeft size={18} /> All missions
        </Link>
        <span className={styles.liveStatus}><i /> Mission control</span>
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

      <AnimatePresence>
        {busy && (
          <motion.div
            className={styles.workspaceFocusBackdrop}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.32, ease: "easeOut" }}
            role="status"
            aria-label="AI workspace is building your mission"
          >
            <motion.div
              className={styles.workspaceFocusSurface}
              initial={{ opacity: 0, y: 34, scale: 0.94 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -16, scale: 0.98 }}
              transition={{ duration: 0.56, ease: [0.22, 1, 0.36, 1] }}
            >
              <AIProgressPanel busy={busy} complete={complete} activeStep={progressStep} focus />
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {showBundleReady && items.length > 0 && (
          <motion.div
            className={styles.bundleReadyBackdrop}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.24 }}
            role="status"
            aria-live="polite"
            aria-label="Your recommendations are ready"
            onClick={revealBundle}
          >
            <motion.div
              className={styles.bundleReadyCard}
              initial={reduceMotion ? { opacity: 0 } : { opacity: 0, y: 24, scale: 0.92 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={reduceMotion ? { opacity: 0 } : { opacity: 0, y: -12, scale: 0.97 }}
              transition={{ duration: 0.42, ease: [0.22, 1, 0.36, 1] }}
              onClick={(event) => event.stopPropagation()}
            >
              <span className={styles.bundleReadyIcon}><CircleCheck size={34} /></span>
              <small>RECOMMENDATION COMPLETE</small>
              <h2>Your verified selection is ready.</h2>
              <p>{items.length} catalog-verified {items.length === 1 ? "item is" : "items are"} ready for review.</p>
              {priceSummary && <strong>{priceSummary.label}</strong>}
              <button type="button" onClick={revealBundle}>View recommendations</button>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

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
            ref={resultsRef}
            key="results"
            initial={{ opacity: 0, y: 26, scale: 0.99 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{ duration: 0.55, ease: [0.22, 1, 0.36, 1] }}
          >
            <div className={styles.resultHeading}>
              <span>VERIFIED OUTPUT</span>
              <h2>Your recommendation, ready for review.</h2>
              {priceSummary && <strong>{priceSummary.label}</strong>}
            </div>
            <OptimizationActions disabled={busy} onPick={refine} />
            <form className={styles.feedbackForm} onSubmit={(event) => { event.preventDefault(); refine(feedback); }}>
              <label htmlFor="bundle-feedback">Not quite right?</label>
              <div>
                <input
                  id="bundle-feedback"
                  value={feedback}
                  disabled={busy}
                  onChange={(event) => setFeedback(event.target.value)}
                  placeholder="Tell AI what to change — for example, fewer items, warmer style, or a lower total."
                />
                <button type="submit" disabled={busy || !feedback.trim()}>Improve bundle</button>
              </div>
              <p>Shopy keeps this mission in short-term memory so each revision starts from your last brief.</p>
            </form>
            {items.length ? (
              <BundleBoard items={items} mission={mission} workspace={bundleWorkspace} adding={adding} addingProductId={addingProductId} onAdd={() => void addBundle()} onAddItem={(productId) => void addRecommendation(productId)} onRemove={removeBundleItem} />
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
