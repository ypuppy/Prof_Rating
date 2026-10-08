import { request } from "./client";

export function requestLoginCode(email) {
  return request("/auth/request-code", { method: "POST", body: { email } });
}

export function verifyLoginCode(email, code) {
  return request("/auth/verify", { method: "POST", body: { email, code } });
}

export function fetchCurrentUser() {
  return request("/auth/me");
}

export function logout() {
  return request("/auth/logout", { method: "POST" });
}
