import type { Attachment, BundleWorkspace, MissionData, MissionHistoryItem } from "./types";

export const workspaceStorageKey = "shopy:mission-workspace:v2";

export type StoredMissionWorkspace = {
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

function attachment(value: unknown): Attachment | null {
  if (!isRecord(value)
    || typeof value.product_id !== "string"
    || typeof value.name !== "string"
    || (typeof value.price !== "string" && typeof value.price !== "number")
    || typeof value.currency !== "string"
    || typeof value.image_url !== "string") {
    return null;
  }
  return value as Attachment;
}

function historyItem(value: unknown): MissionHistoryItem | null {
  if (!isRecord(value)
    || typeof value.id !== "string"
    || typeof value.label !== "string"
    || typeof value.price_label !== "string"
    || typeof value.at !== "string") {
    return null;
  }
  return value as MissionHistoryItem;
}

/**
 * Recover the useful portion of a completed mission instead of discarding the
 * whole response because one optional product or workspace field is malformed.
 */
export function normalizeStoredWorkspace(value: unknown): StoredMissionWorkspace | null {
  if (!isRecord(value)
    || value.version !== 2
    || typeof value.routeMission !== "string"
    || typeof value.request !== "string"
    || typeof value.analysis !== "string"
    || !value.analysis.trim()) {
    return null;
  }

  return {
    version: 2,
    routeMission: value.routeMission,
    request: value.request,
    analysis: value.analysis,
    mission: isRecord(value.mission) ? value.mission as MissionData : {},
    items: Array.isArray(value.items)
      ? value.items.map(attachment).filter((item): item is Attachment => item !== null)
      : [],
    workspace: isRecord(value.workspace) ? value.workspace as BundleWorkspace : {},
    history: Array.isArray(value.history)
      ? value.history.map(historyItem).filter((item): item is MissionHistoryItem => item !== null)
      : [],
  };
}

export function readStoredWorkspace(key = workspaceStorageKey): StoredMissionWorkspace | null {
  try {
    const raw = window.sessionStorage.getItem(key);
    return raw ? normalizeStoredWorkspace(JSON.parse(raw)) : null;
  } catch {
    return null;
  }
}

export function writeStoredWorkspace(snapshot: StoredMissionWorkspace, key = workspaceStorageKey): boolean {
  try {
    window.sessionStorage.setItem(key, JSON.stringify(snapshot));
    return true;
  } catch {
    return false;
  }
}

export function visionHandoffStorageKey(id: string): string {
  return `shopy:vision-mission:${id}`;
}
