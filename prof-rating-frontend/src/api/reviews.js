const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";

export async function fetchReviews(professorId, { limit = 50 } = {}) {
  const url = new URL(`${API_BASE}/professors/${professorId}/reviews`);
  url.searchParams.set("limit", String(limit));

  const res = await fetch(url.toString());
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Failed to fetch reviews");
  return data.items;
}

export async function createReview(professorId, payload) {
  const res = await fetch(`${API_BASE}/professors/${professorId}/reviews`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Failed to create review");
  return data;
}
