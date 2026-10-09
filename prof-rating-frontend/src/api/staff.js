import { request } from "./client";

/** People from department websites. professor_id is set when they already have a page here. */
export async function searchStaff(query) {
  const data = await request("/staff/search", { params: { query } });
  return data.items;
}
