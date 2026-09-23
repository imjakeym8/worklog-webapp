import { apiFetch, apiFetchBlob } from "@/lib/api";
import type {
  WorklogAttachment,
  WorklogEntry,
  WorklogInput,
  WorklogUpdateInput,
} from "@/types";

interface WorklogListResponse {
  items: WorklogEntry[];
  nextCursor: string | null;
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === "string");
}

function isWorklogEntry(value: unknown): value is WorklogEntry {
  if (!value || typeof value !== "object") {
    return false;
  }

  const worklog = value as Record<string, unknown>;
  return (
    typeof worklog.id === "string" &&
    typeof worklog.date === "string" &&
    typeof worklog.hours === "number" &&
    typeof worklog.shipped === "boolean" &&
    (worklog.visibility === "public" || worklog.visibility === "private") &&
    isStringArray(worklog.tracks) &&
    isStringArray(worklog.blockers) &&
    isStringArray(worklog.next) &&
    typeof worklog.activityBreakdown === "string" &&
    typeof worklog.detailedNotes === "string" &&
    typeof worklog.quickSummary === "string" &&
    (worklog.attachment === null || isWorklogAttachment(worklog.attachment)) &&
    typeof worklog.createdAt === "string" &&
    typeof worklog.updatedAt === "string"
  );
}

function isWorklogAttachment(value: unknown): value is WorklogAttachment {
  if (!value || typeof value !== "object") {
    return false;
  }
  const attachment = value as Record<string, unknown>;
  return (
    typeof attachment.id === "string" &&
    typeof attachment.worklogId === "string" &&
    typeof attachment.originalFilename === "string" &&
    (attachment.contentType === "image/jpeg" || attachment.contentType === "image/png") &&
    typeof attachment.sizeBytes === "number" &&
    typeof attachment.width === "number" &&
    typeof attachment.height === "number" &&
    typeof attachment.createdAt === "string"
  );
}

function parseWorklog(value: unknown): WorklogEntry {
  if (!isWorklogEntry(value)) {
    throw new Error("FastAPI returned an invalid worklog response.");
  }

  return value;
}

function parseWorklogList(value: unknown): WorklogListResponse {
  if (!value || typeof value !== "object") {
    throw new Error("FastAPI returned an invalid worklog list.");
  }

  const response = value as Record<string, unknown>;
  if (
    !Array.isArray(response.items) ||
    !response.items.every(isWorklogEntry) ||
    (response.nextCursor !== null && typeof response.nextCursor !== "string")
  ) {
    throw new Error("FastAPI returned an invalid worklog list.");
  }

  return {
    items: response.items,
    nextCursor: response.nextCursor,
  };
}

export async function getWorklogs(): Promise<WorklogEntry[]> {
  const worklogs: WorklogEntry[] = [];
  let nextCursor: string | null = null;

  do {
    const query = new URLSearchParams({ limit: "100" });
    if (nextCursor) {
      query.set("cursor", nextCursor);
    }

    const response = parseWorklogList(
      await apiFetch<unknown>(`/api/worklogs?${query.toString()}`),
    );
    worklogs.push(...response.items);
    nextCursor = response.nextCursor;
  } while (nextCursor);

  return worklogs;
}

export async function createWorklog(input: WorklogInput): Promise<WorklogEntry> {
  return parseWorklog(
    await apiFetch<unknown>("/api/worklogs", {
      method: "POST",
      body: JSON.stringify(input),
    }),
  );
}

export async function updateWorklog(
  worklogId: string,
  input: WorklogUpdateInput,
): Promise<WorklogEntry> {
  return parseWorklog(
    await apiFetch<unknown>(`/api/worklogs/${encodeURIComponent(worklogId)}`, {
      method: "PATCH",
      body: JSON.stringify(input),
    }),
  );
}

export async function deleteWorklog(worklogId: string): Promise<void> {
  await apiFetch<void>(`/api/worklogs/${encodeURIComponent(worklogId)}`, {
    method: "DELETE",
  });
}

function attachmentRequest(file: File): RequestInit {
  const formData = new FormData();
  formData.append("upload", file);
  return { body: formData };
}

function parseAttachment(value: unknown): WorklogAttachment {
  if (!isWorklogAttachment(value)) {
    throw new Error("FastAPI returned an invalid attachment response.");
  }
  return value;
}

export async function createWorklogAttachment(
  worklogId: string,
  file: File,
): Promise<WorklogAttachment> {
  return parseAttachment(
    await apiFetch<unknown>(`/api/worklogs/${encodeURIComponent(worklogId)}/attachment`, {
      method: "POST",
      ...attachmentRequest(file),
    }),
  );
}

export async function replaceWorklogAttachment(
  worklogId: string,
  file: File,
): Promise<WorklogAttachment> {
  return parseAttachment(
    await apiFetch<unknown>(`/api/worklogs/${encodeURIComponent(worklogId)}/attachment`, {
      method: "PUT",
      ...attachmentRequest(file),
    }),
  );
}

export async function deleteWorklogAttachment(worklogId: string): Promise<void> {
  await apiFetch<void>(`/api/worklogs/${encodeURIComponent(worklogId)}/attachment`, {
    method: "DELETE",
  });
}

export async function getWorklogAttachmentPreview(worklogId: string): Promise<Blob> {
  return apiFetchBlob(`/api/worklogs/${encodeURIComponent(worklogId)}/attachment`);
}

export async function importMarkdownWorklog(file: File, update = false): Promise<WorklogEntry> {
  const formData = new FormData();
  formData.append("upload", file);
  formData.append("update", String(update));
  return parseWorklog(
    await apiFetch<unknown>("/api/imports/markdown", { method: "POST", body: formData }),
  );
}

export async function getWorklogMarkdown(worklogId: string): Promise<Blob> {
  return apiFetchBlob(`/api/worklogs/${encodeURIComponent(worklogId)}/markdown`);
}
