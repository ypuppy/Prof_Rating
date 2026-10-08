import { request } from "./client";

export async function fetchMyReviews() {
  const data = await request("/me/reviews");
  return data.items;
}

/** Deletes one of my reviews; resolves to the temporarily cached copy. */
export function deleteMyReview(reviewId) {
  return request(`/me/reviews/${reviewId}`, { method: "DELETE" });
}

export async function fetchDeletedReviews() {
  const data = await request("/me/deleted-reviews");
  return data.items;
}

export function discardDeletedReview(deletedId) {
  return request(`/me/deleted-reviews/${deletedId}`, { method: "DELETE" });
}
