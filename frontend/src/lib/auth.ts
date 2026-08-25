import { API_URL } from "@/lib/api";

export const AUTH_CHANGE_EVENT = "shopy-auth-change";

export type AuthUser = {
  id: string;
  email: string;
  full_name: string;
  avatar_url: string | null;
  status: "active" | "suspended" | "deleted";
  created_at: string;
};

type AuthResponse = {
  user: AuthUser;
};

async function parseError(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as {
      detail?: string | Array<{ msg?: string }>;
    };
    if (typeof payload.detail === "string") return payload.detail;
    if (Array.isArray(payload.detail)) {
      return payload.detail.map((item) => item.msg).filter(Boolean).join(" ");
    }
  } catch {
    // Fall through to a stable message when the API returns no JSON body.
  }
  return "Something went wrong. Please try again.";
}

async function authFetch(path: string, init?: RequestInit): Promise<Response> {
  return fetch(`${API_URL}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...init?.headers,
    },
  });
}

export async function registerAccount(input: {
  full_name: string;
  email: string;
  password: string;
}): Promise<AuthUser> {
  const response = await authFetch("/api/v1/auth/register", {
    method: "POST",
    body: JSON.stringify(input),
  });
  if (!response.ok) throw new Error(await parseError(response));
  return ((await response.json()) as AuthResponse).user;
}

export async function loginAccount(input: {
  email: string;
  password: string;
}): Promise<AuthUser> {
  const response = await authFetch("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify(input),
  });
  if (!response.ok) throw new Error(await parseError(response));
  return ((await response.json()) as AuthResponse).user;
}

export async function getCurrentUser(): Promise<AuthUser | null> {
  const response = await authFetch("/api/v1/auth/me", { cache: "no-store" });
  if (response.status === 401 || response.status === 403) return null;
  if (!response.ok) throw new Error(await parseError(response));
  return (await response.json()) as AuthUser;
}

export async function logoutAccount(): Promise<void> {
  const response = await authFetch("/api/v1/auth/logout", { method: "POST" });
  if (!response.ok) throw new Error(await parseError(response));
}

export function notifyAuthChanged(): void {
  window.dispatchEvent(new Event(AUTH_CHANGE_EVENT));
}

export function getSafeReturnPath(value: string | null): string {
  return value && value.startsWith("/") && !value.startsWith("//")
    ? value
    : "/profile";
}
