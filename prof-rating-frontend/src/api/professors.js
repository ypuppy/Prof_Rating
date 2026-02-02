const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";

export async function fetchProfessors({ query = "", limit = 100 } = {}) {
  const url = new URL(`${API_BASE}/professors`);
  if (query) url.searchParams.set("query", query);
  url.searchParams.set("limit", String(limit));

  const res = await fetch(url.toString());
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Failed to fetch professors");
  return data.items;
}

export async function fetchProfessorDetail(id) {
  const res = await fetch(`${API_BASE}/professors/${id}`);
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Failed to fetch professor");
  return data;
}
