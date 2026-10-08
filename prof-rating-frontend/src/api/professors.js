import { request } from "./client";

export async function fetchProfessors({ query = "", limit = 100 } = {}) {
  const data = await request("/professors", { params: { query, limit } });
  return data.items;
}

export function fetchProfessorDetail(id) {
  return request(`/professors/${id}`);
}

export function createProfessor(payload) {
  return request("/professors", { method: "POST", body: payload });
}
