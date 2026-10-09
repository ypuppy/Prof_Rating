const API_BASE = import.meta.env.VITE_API_BASE || "/api";

/** Thrown for any non-2xx response; `status` lets callers react to 401 etc., `data` is the response body. */
export class ApiError extends Error {
  constructor(message, status, data = null) {
    super(message);
    this.status = status;
    this.data = data;
  }
}

export async function request(path, { method = "GET", body, params } = {}) {
  const url = new URL(`${API_BASE}${path}`, window.location.origin);
  for (const [key, value] of Object.entries(params || {})) {
    if (value !== undefined && value !== null && value !== "") url.searchParams.set(key, String(value));
  }

  let res;
  try {
    res = await fetch(url, {
      method,
      credentials: "include",
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError("Can't reach the server. Is the backend running?", 0);
  }

  const data = await res.json().catch(() => null);
  if (!res.ok) {
    // FastAPI validation errors put a list in `detail`; some of our errors put an object with `message`
    const raw = data?.detail;
    const detail = Array.isArray(raw) ? raw[0]?.msg : typeof raw === "object" && raw ? raw.message : raw;
    throw new ApiError(detail || `Request failed (${res.status})`, res.status, data);
  }
  return data;
}
