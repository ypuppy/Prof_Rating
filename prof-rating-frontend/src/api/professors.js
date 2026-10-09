import { request } from "./client";

export async function fetchProfessors({ query = "", limit = 100 } = {}) {
  const data = await request("/professors", { params: { query, limit } });
  return data.items;
}

export function fetchProfessorDetail(id) {
  return request(`/professors/${id}`);
}

/** Existing professors who may be the person called `name`; each has match: "same" | "similar". */
export async function findSimilarProfessors(name) {
  const data = await request("/professors/similar", { params: { name } });
  return data.items;
}

export function createProfessor(payload) {
  return request("/professors", { method: "POST", body: payload });
}
