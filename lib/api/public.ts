import { apiFetch, apiFetchBlob } from "@/lib/api";
import type { WorklogEntry } from "@/types";

export interface PublicProfile {
  githubLogin: string;
  githubAvatarUrl: string | null;
  githubProfileUrl: string;
}

interface PublicResponse {
  items: Array<Omit<WorklogEntry, "visibility" | "createdAt" | "updatedAt" | "attachment"> & {
    attachment: { originalFilename: string } | null;
  }>;
  nextCursor: string | null;
}

function toEntry(entry: PublicResponse["items"][number]): WorklogEntry {
  return {
    ...entry,
    visibility: "public",
    createdAt: "",
    updatedAt: "",
    attachment: entry.attachment
      ? {
          id: "",
          worklogId: entry.id,
          originalFilename: entry.attachment.originalFilename,
          contentType: "image/jpeg",
          sizeBytes: 0,
          width: 0,
          height: 0,
          createdAt: "",
        }
      : null,
  };
}

export async function getPublicWorklogs(): Promise<WorklogEntry[]> {
  const worklogs: WorklogEntry[] = [];
  let nextCursor: string | null = null;
  do {
    const query = new URLSearchParams({ limit: "100" });
    if (nextCursor) query.set("cursor", nextCursor);
    const response = await apiFetch<PublicResponse>(`/api/public/worklogs?${query}`);
    worklogs.push(...response.items.map(toEntry));
    nextCursor = response.nextCursor;
  } while (nextCursor);
  return worklogs;
}

export function getPublicWorklogAttachment(worklogId: string): Promise<Blob> {
  return apiFetchBlob(`/api/public/worklogs/${encodeURIComponent(worklogId)}/attachment`);
}

export function getPublicProfile(): Promise<PublicProfile | null> {
  return apiFetch<PublicProfile | null>("/api/public/profile");
}
