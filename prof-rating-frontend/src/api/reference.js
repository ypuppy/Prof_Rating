import { request } from "./client";

export async function searchFaculties(query) {
  const data = await request("/reference/faculties", { params: { query } });
  return data.items;
}

export async function searchDepartments(query, faculty) {
  const data = await request("/reference/departments", { params: { query, faculty } });
  return data.items;
}

export async function searchModules(query) {
  const data = await request("/reference/modules", { params: { query } });
  return data.items;
}
