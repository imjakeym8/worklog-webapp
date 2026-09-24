import { APIError, API_URL, apiFetch } from "@/lib/api";
import type { CurrentUser } from "@/types";

function isCurrentUser(value: unknown): value is CurrentUser {
  if (!value || typeof value !== "object") {
    return false;
  }
  const user = value as Record<string, unknown>;
  return (
    typeof user.id === "string" &&
    typeof user.githubLogin === "string" &&
    (user.displayName === null || typeof user.displayName === "string") &&
    (user.avatarUrl === null || typeof user.avatarUrl === "string") &&
    typeof user.isAdmin === "boolean"
  );
}

export async function getCurrentUser(): Promise<CurrentUser | null> {
  try {
    const user = await apiFetch<unknown>("/api/auth/me");
    if (!isCurrentUser(user)) {
      throw new Error("FastAPI returned an invalid current-user response.");
    }
    return user;
  } catch (error) {
    if (error instanceof APIError && error.status === 401) {
      return null;
    }
    throw error;
  }
}

export const GITHUB_LOGIN_URL = `${API_URL}/api/auth/github`;
export const GITHUB_ADMIN_LOGIN_URL = `${GITHUB_LOGIN_URL}?next=%2Fadmin`;

export async function logout(): Promise<void> {
  await apiFetch<void>("/api/auth/logout", { method: "POST" });
}
