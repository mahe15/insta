let csrf = "";
export const setCsrf = (value: string) => {
  csrf = value;
};
export async function api<T = Record<string, unknown>>(
  path: string,
  method = "GET",
  data?: unknown,
): Promise<T> {
  const form = data instanceof FormData;
  const response = await fetch("/api" + path, {
    method,
    credentials: "same-origin",
    headers: {
      ...(data && !form ? { "Content-Type": "application/json" } : {}),
      ...(method !== "GET" ? { "X-CSRF-Token": csrf } : {}),
    },
    body: data ? (form ? data : JSON.stringify(data)) : undefined,
  });
  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: "The server could not complete that request." }));
    if (response.status === 401 && !["/session", "/bootstrap"].includes(path))
      window.dispatchEvent(new Event("session-expired"));
    throw new Error(
      typeof error.detail === "string"
        ? error.detail
        : "Check the highlighted values and try again.",
    );
  }
  return response.json();
}
export function upload(path: string, file: File) {
  const form = new FormData();
  form.append("file", file);
  return api(path, "POST", form);
}
export const providerName = (id: string | null) =>
  ({
    chatgpt_browser: "ChatGPT · browser",
    gemini: "Gemini API",
    xai: "Grok",
    openai: "OpenAI",
    heuristic: "Offline ranking",
  })[id || ""] || "Default provider";
export const seconds = (value: number = 0) => {
  const n = Math.max(0, Math.round(value));
  return n >= 3600
    ? `${Math.floor(n / 3600)}:${String(Math.floor(n / 60) % 60).padStart(2, "0")}:${String(n % 60).padStart(2, "0")}`
    : `${Math.floor(n / 60)}:${String(n % 60).padStart(2, "0")}`;
};
export const when = (time: number) =>
  new Date(time * 1000).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
export const dateTime = (time: number) =>
  new Date(time * 1000).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
export const humanState = (state: string) =>
  ({
    queued_analysis: "Queued",
    analyzing: "Finding moments",
    awaiting_selection: "Ready to review",
    queued_render: "Render queued",
    rendering: "Rendering",
    complete: "Completed",
    failed: "Needs attention",
    cancelled: "Cancelled",
    approval: "Awaiting approval",
    queued: "Scheduled",
    preparing: "Preparing",
    publishing: "Publishing",
    published: "Published",
    rejected: "Rejected",
    uncertain: "Check Instagram",
    running: "In production",
    ready: "Ready",
  })[state] || state;
