export const API_URL =
  process.env.NEXT_PUBLIC_BACKEND_API_URL ??
  process.env.NEXT_PUBLIC_ASSISTANT_API_URL ??
  "";

export async function apiErrorMessage(response: Response, fallback: string) {
  const text = await response.text().catch(() => "");
  if (!text.trim()) return fallback;
  try {
    const body = JSON.parse(text) as { detail?: unknown };
    if (typeof body.detail === "string" && body.detail.trim()) return body.detail;
  } catch {
    // Proxies sometimes return a plain-text or HTML error document. Do not
    // expose that transport response as a misleading JSON parsing failure.
  }
  return response.status < 500 ? text.trim() : fallback;
}

export async function apiFetch(path: string, init?: RequestInit) {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    credentials: "include",
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    throw new Error(await apiErrorMessage(response, "Unable to complete this request."));
  }
  return response.status === 204 ? null : response.json();
}
