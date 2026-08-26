"use client";

import Link from "next/link";
import { ArrowLeft, RefreshCw, Sparkles } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { useMemo, useState } from "react";
import { API_URL, apiFetch } from "@/lib/api";
import AIProgressPanel from "./AIProgressPanel";
import AlternativeBundles from "./AlternativeBundles";
import BundleBoard from "./BundleBoard";
import MissionCards from "./MissionCards";
import MissionHistory from "./MissionHistory";
import MissionInputPanel from "./MissionInputPanel";
import OptimizationActions from "./OptimizationActions";
import { Attachment, BundleWorkspace, MissionData, MissionHistoryItem } from "./types";
import styles from "./mission-workspace.module.css";
import heroStyles from "./hero-enhancement.module.css";

const emptyMission: MissionData = { preferences: [], owned_items: [], priorities: [] };

function draftMission(text: string): MissionData {
  const budget = text.match(/(?:under|below|budget(?:\s+of)?|within)\s*(?:rm)?\s*([\d,]+)/i)?.[1];
  const owned = text.match(/(?:already own|i have|with my)\s+([^.,]+)/i)?.[1]?.split(/,| and /i).map((item) => item.trim()).filter(Boolean) ?? [];
  const preferenceTerms = ["minimal", "comfortable", "wireless", "warm", "ergonomic", "best value", "smart casual"].filter((term) => text.toLowerCase().includes(term));
  return { budget: budget ? Number(budget.replaceAll(",", "")) : null, preferences: preferenceTerms, owned_items: owned };
}

export default function MissionWorkspace() {
  const search = useSearchParams();
  const [request, setRequest] = useState(search.get("mission") ?? "");
  const [mission, setMission] = useState<MissionData>(() => draftMission(search.get("mission") ?? ""));
  const [busy, setBusy] = useState(false); const [analysis, setAnalysis] = useState(""); const [items, setItems] = useState<Attachment[]>([]); const [bundleWorkspace, setBundleWorkspace] = useState<BundleWorkspace>({}); const [error, setError] = useState(""); const [adding, setAdding] = useState(false); const [history, setHistory] = useState<MissionHistoryItem[]>([]);
  const complete = Boolean(analysis);
  const total = useMemo(() => items.reduce((sum, item) => sum + Number(item.price), 0), [items]);
  const runMission = async (nextRequest = request) => {
    if (!nextRequest.trim()) return;
    setBusy(true); setError(""); setAnalysis(""); setItems([]); setBundleWorkspace({});
    try {
      const response = await fetch(`${API_URL}/api/chat`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ messages: [{ role: "user", content: nextRequest.trim() }] }) });
      const data = await response.json() as { reply?: string; detail?: string; attachments?: Attachment[]; mission?: MissionData; workspace?: BundleWorkspace };
      if (!response.ok || !data.reply) throw new Error(data.detail ?? "We could not complete that mission right now.");
      setAnalysis(data.reply); setItems(data.attachments ?? []); setBundleWorkspace(data.workspace ?? {}); setMission({ ...emptyMission, ...data.mission }); setHistory((previous) => [{ id: crypto.randomUUID(), label: data.mission?.goal || nextRequest, total: (data.attachments ?? []).reduce((sum, item) => sum + Number(item.price), 0), at: "Just now" }, ...previous].slice(0, 5));
    } catch (reason) { setError(reason instanceof Error ? reason.message : "We could not complete that mission right now."); } finally { setBusy(false); }
  };
  const removeOwned = (item: string) => setMission((current) => ({ ...current, owned_items: (current.owned_items ?? []).filter((owned) => owned !== item) }));
  const refine = (instruction: string) => { const next = `${request.trim()}. ${instruction}.`; setRequest(next); void runMission(next); };
  const addBundle = async () => { if (!items.length) return; setAdding(true); try { await Promise.all(items.map((item) => apiFetch("/api/v1/cart/items", { method: "POST", body: JSON.stringify({ product_id: item.product_id, quantity: 1 }) }))); } finally { setAdding(false); } };
  return <main className={styles.page}><Link className={styles.back} href="/"><ArrowLeft size={16} /> Back to missions</Link><header className={`${styles.hero} ${heroStyles.hero}`}><div className={heroStyles.heroCopy}><span><Sparkles size={14} /> SHOPY MISSION CONTROL</span><h1>From intent to <em>the right setup.</em></h1><p>Describe the outcome once. Shopy turns it into a clear brief, verifies the details, and gives you options worth acting on.</p><div className={heroStyles.heroSignals}><span><i />Goal-first planning</span><span><i />Catalog-verified</span><span><i />Built around you</span></div></div><div className={heroStyles.heroConsole} aria-label="Mission workflow preview"><div><span>MISSION STATUS</span><strong>Ready for your brief</strong></div><ol><li><b>01</b> Understand the outcome</li><li><b>02</b> Build the evidence</li><li><b>03</b> Shape your bundle</li></ol><small>NO KEYWORDS. NO NOISE. JUST A PLAN.</small></div></header><MissionCards onPick={(prompt) => { setRequest(prompt); setMission(draftMission(prompt)); }} /><MissionInputPanel request={request} mission={mission} busy={busy} onRequestChange={(value) => { setRequest(value); setMission(draftMission(value)); }} onLaunch={() => void runMission()} onRemoveOwned={removeOwned} /><section className={styles.workspace}><AIProgressPanel busy={busy} complete={complete} /><div className={styles.workspaceContent}>{error && <div className={styles.error}><strong>Mission paused.</strong><p>{error}</p><button type="button" onClick={() => void runMission()}><RefreshCw size={14} /> Try again</button></div>}{complete && <><OptimizationActions disabled={busy} onPick={refine} />{items.length ? <BundleBoard items={items} mission={mission} workspace={bundleWorkspace} adding={adding} onAdd={() => void addBundle()} /> : <section className={styles.insight}><span>MISSION INSIGHT</span><p>{analysis}</p></section>}<AlternativeBundles items={items} onExplore={refine} /></>}</div></section><MissionHistory entries={history} onRestore={(label) => { setRequest(label); setMission(draftMission(label)); }} /><span className={styles.sessionTotal} aria-hidden="true">{complete ? `Current bundle · RM ${total.toLocaleString("en-MY", { maximumFractionDigits: 0 })}` : ""}</span></main>;
}
