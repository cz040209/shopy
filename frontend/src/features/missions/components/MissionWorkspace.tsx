"use client";

import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { ArrowLeft, CircleCheck, RefreshCw, WandSparkles } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { API_URL, apiErrorMessage, apiFetch } from "@/lib/api";
import { useCart } from "@/features/cart/cart-context";
import AIProgressPanel from "./AIProgressPanel";
import AlternativeBundles from "./AlternativeBundles";
import BundleBoard from "./BundleBoard";
import MissionHistory from "./MissionHistory";
import MissionInputPanel from "./MissionInputPanel";
import OptimizationActions from "./OptimizationActions";
import { recommendationPriceSummary } from "./pricing";
import { Attachment, BundleWorkspace, MissionData, MissionHistoryItem } from "./types";
import {
  readStoredWorkspace,
  visionHandoffStorageKey,
  workspaceStorageKey,
  writeStoredWorkspace,
} from "./workspace-storage";
import type { StoredMissionWorkspace } from "./workspace-storage";
import styles from "./mission-studio.module.css";

const emptyMission: MissionData = { preferences: [], owned_items: [], priorities: [] };
const progressStepCount = 6;
const stageDurationMs = 1800;
type MissionStreamEvent =
  | { type: "start" | "progress" }
  | { type: "delta"; delta?: string }
  | {
      type: "done";
      attachments?: Attachment[];
      mission?: MissionData;
      workspace?: BundleWorkspace;
    }
  | { type: "error"; detail?: string };
const uniquePhrases = (values: string[]) => Array.from(new Map(
  values
    .map((value) => value.replace(/\s+/g, " ").replace(/^[\s,.:;-]+|[\s,.:;-]+$/g, "").trim())
    .filter((value) => value.length > 1)
    .map((value) => [value.toLocaleLowerCase(), value] as const),
).values());

/**
 * Provides immediate feedback while the customer types. This intentionally
 * identifies language structure (budget, ownership, goals, and qualifiers),
 * rather than maintaining a brittle list of product categories or adjectives.
 * The server remains the authoritative interpreter when the mission is run.
 */
function draftMission(text: string): MissionData {
  const request = text.replace(/\s+/g, " ").trim();
  const budgetMatch = request.match(/(?:\b(?:rm|myr)\s*|\b(?:under|below|within|around|budget(?:\s+of)?)\s*(?:rm|myr)?\s*)([\d][\d,]*(?:\.\d{1,2})?)/i);
  const budgetValue = budgetMatch ? Number(budgetMatch[1].replaceAll(",", "")) : null;
  const ownedMatches = Array.from(request.matchAll(/\b(?:already\s+own|i\s+own|i\s+have|with\s+my)\s+(.+?)(?=\s+(?:and\s+)?(?:prefer(?:ably)?|need|want|must|should|with|without|but)\b|[.!?;]|$)/gi));
  const owned = uniquePhrases(ownedMatches.flatMap((match) => match[1].split(/\s*,\s*|\s+and\s+/i)));
  const withoutMetadata = request
    .replace(/\b(?:already\s+own|i\s+own|i\s+have|with\s+my)\s+.+?(?=\s+(?:and\s+)?(?:prefer(?:ably)?|need|want|must|should|with|without|but)\b|[.!?;]|$)/gi, "")
    .replace(/(?:\b(?:rm|myr)\s*|\b(?:under|below|within|around|budget(?:\s+of)?)\s*(?:rm|myr)?\s*)[\d][\d,]*(?:\.\d{1,2})?/gi, "")
    .replace(/\s+/g, " ")
    .replace(/\s+([,.;!?])/g, "$1")
    .trim();

  const goal = withoutMetadata
    .replace(/^\s*(?:can\s+you\s+)?(?:please\s+)?(?:help\s+me\s+)?(?:i\s+(?:need|want|would\s+like)\s+to\s+|(?:find|build|create|plan|prepare|recommend)\s+(?:me\s+)?)/i, "")
    .replace(/\b(?:for|with|without|prefer(?:ably)?|but)\b[\s\S]*$/i, "")
    .replace(/^\s*(?:a|an|the)\s+/i, "")
    .trim();

  const qualifiers = Array.from(withoutMetadata.matchAll(/\b(?:for|with|without|prefer(?:ably)?|must|should|but)\s+([^.!?;]+)/gi))
    .map((match) => match[1]);
  const keyRequirements = uniquePhrases([goal, ...qualifiers]).slice(0, 6);

  return {
    budget: Number.isFinite(budgetValue) ? budgetValue : null,
    preferences: uniquePhrases(qualifiers).slice(0, 6),
    key_requirements: keyRequirements,
    owned_items: owned,
  };
}

export default function MissionWorkspace() {
  const search = useSearchParams();
  const reduceMotion = useReducedMotion();
  const initialRequest = search.get("mission") ?? "";
  const autoRunId = search.get("autorun") ?? "";
  const visionHandoffId = search.get("vision") ?? "";
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
  const autoRunStartedRef = useRef(false);
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
    const handoff = visionHandoffId
      ? readStoredWorkspace(visionHandoffStorageKey(visionHandoffId))
      : null;
    if (autoRunId) {
      try {
        if (window.sessionStorage.getItem(`shopy:auto-mission:${autoRunId}`) !== "started") return;
      } catch {
        return;
      }
    }
    const stored = handoff ?? readStoredWorkspace();
    // A mission supplied in the URL represents a new brief unless it matches
    // the saved workspace (as it does when returning from a product page).
    if (!stored || stored.routeMission !== initialRequest) {
      if (!visionHandoffId) return;
      const errorFrame = window.requestAnimationFrame(() => {
        setError("The completed photo result could not be restored. Please return and try the photo again.");
      });
      return () => window.cancelAnimationFrame(errorFrame);
    }
    const frame = window.requestAnimationFrame(() => {
      setRequest(stored.request);
      setAnalysis(stored.analysis);
      setMission({ ...emptyMission, ...stored.mission });
      setItems(stored.items);
      setBundleWorkspace(stored.workspace);
      setHistory(stored.history.slice(0, 5));
      setProgressStep(progressStepCount);
      if (visionHandoffId) {
        // Commit the canonical copy before consuming the one-time handoff.
        // This ordering also survives React's development effect replay.
        writeStoredWorkspace(stored, workspaceStorageKey);
        try {
          window.sessionStorage.removeItem(visionHandoffStorageKey(visionHandoffId));
        } catch {
          // Leaving an already-consumed handoff is harmless.
        }
      }
    });
    return () => window.cancelAnimationFrame(frame);
  }, [autoRunId, initialRequest, visionHandoffId]);

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
    writeStoredWorkspace(snapshot, workspaceStorageKey);
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

  const runMission = useCallback(async (nextRequest?: string) => {
    const missionRequest = (nextRequest ?? request).trim();
    if (!missionRequest) return;
    const startedAt = performance.now();
    setBusy(true);
    setProgressStep(0);
    setError("");
    setAnalysis("");
    setItems([]);
    setBundleWorkspace({});
    setShowBundleReady(false);

    try {
      const response = await fetch(`${API_URL}/api/chat/stream`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: [{ role: "user", content: missionRequest }] }),
      });
      if (!response.ok || !response.body) {
        throw new Error(await apiErrorMessage(
          response,
          "The mission connection closed before the recommendation was ready. Please try again.",
        ));
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let reply = "";
      let completed: Extract<MissionStreamEvent, { type: "done" }> | null = null;
      const applyEvent = (line: string) => {
        let event: MissionStreamEvent;
        try {
          event = JSON.parse(line) as MissionStreamEvent;
        } catch {
          throw new Error("The mission response stream was interrupted. Please try again.");
        }
        if (event.type === "error") {
          throw new Error(event.detail ?? "We could not complete that mission right now.");
        }
        if (event.type === "delta" && event.delta) reply += event.delta;
        if (event.type === "done") completed = event;
      };

      try {
        while (true) {
          const { value, done } = await reader.read();
          buffer += decoder.decode(value, { stream: !done });
          const lines = buffer.split("\n");
          buffer = lines.pop() ?? "";
          for (const line of lines) if (line.trim()) applyEvent(line);
          if (done) break;
        }
        if (buffer.trim()) applyEvent(buffer);
      } catch (streamError) {
        await reader.cancel().catch(() => undefined);
        throw streamError;
      }

      if (!completed || !reply.trim()) {
        throw new Error("The mission response ended before the recommendation was ready. Please try again.");
      }
      const data = {
        reply: reply.trim(),
        attachments: completed.attachments,
        mission: completed.mission,
        workspace: completed.workspace,
      };

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
        label: data.mission?.goal || missionRequest,
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
  }, [request]);

  useEffect(() => {
    if (!autoRunId || !initialRequest.trim() || autoRunStartedRef.current) return;
    const launchKey = `shopy:auto-mission:${autoRunId}`;
    try {
      if (window.sessionStorage.getItem(launchKey) === "started") return;
      window.sessionStorage.setItem(launchKey, "started");
    } catch {
      // The in-memory guard still prevents duplicate launches when storage is unavailable.
    }
    autoRunStartedRef.current = true;
    window.queueMicrotask(() => void runMission(initialRequest));
  }, [autoRunId, initialRequest, runMission]);

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
