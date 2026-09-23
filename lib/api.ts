/**
 * Base URL of the FastAPI backend. Set NEXT_PUBLIC_API_URL in .env.local.
 */
const configuredAPIURL = process.env.NEXT_PUBLIC_API_URL;

if (!configuredAPIURL) {
  throw new Error("NEXT_PUBLIC_API_URL is required. Add it to .env.local.");
}

export const API_URL = configuredAPIURL.replace(/\/$/, "");

interface APIErrorBody {
  error?: {
    code?: string;
    message?: string;
  };
}

export class APIError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code?: string,
  ) {
    super(message);
    this.name = "APIError";
  }
}

/**
 * Thin fetch wrapper so every call gets a consistent base URL, JSON handling,
 * error behavior, and the HTTP-only application session.
 */
export async function apiFetch<T>(
  path: string,
  init?: RequestInit
): Promise<T> {
  const headers = new Headers(init?.headers);
  if (
    init?.body &&
    !(typeof FormData !== "undefined" && init.body instanceof FormData) &&
    !headers.has("Content-Type")
  ) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    credentials: "include",
    headers,
  });

  if (!response.ok) {
    let errorBody: APIErrorBody | undefined;

    try {
      errorBody = (await response.json()) as APIErrorBody;
    } catch {
      // The UI uses a safe fallback when the server does not return JSON.
    }

    throw new APIError(
      errorBody?.error?.message ?? "The API request could not be completed.",
      response.status,
      errorBody?.error?.code,
    );
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

export async function apiFetchBlob(path: string): Promise<Blob> {
  const response = await fetch(`${API_URL}${path}`, { credentials: "include" });
  if (!response.ok) {
    throw new APIError("The image could not be loaded.", response.status);
  }
  return response.blob();
}
