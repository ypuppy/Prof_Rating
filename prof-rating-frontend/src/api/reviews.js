import { request } from "./client";

export async function fetchReviews(professorId, { limit = 50 } = {}) {
  const data = await request(`/professors/${professorId}/reviews`, { params: { limit } });
  return data.items;
}

export function createReview(professorId, payload) {
  return request(`/professors/${professorId}/reviews`, { method: "POST", body: payload });
}
