export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "/api";

function getFetchBaseUrl() {
  if (typeof window !== "undefined") {
    return API_BASE_URL;
  }
  if (API_BASE_URL.startsWith("http")) {
    return API_BASE_URL;
  }
  return process.env.INTERNAL_API_BASE_URL ?? "http://127.0.0.1:8000";
}

function apiUrl(path: string) {
  return `${getFetchBaseUrl()}${path}`;
}

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(apiUrl(path), { cache: "no-store" });
  if (!response.ok) throw new Error(`GET ${path} failed`);
  return response.json();
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(apiUrl(path), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`POST ${path} failed: ${detail}`);
  }
  return response.json();
}
