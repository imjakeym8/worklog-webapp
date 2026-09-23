import { apiFetch } from "@/lib/api";

export interface GitHubRepository {
  id: string;
  fullName: string;
  private: boolean;
  htmlUrl: string;
  defaultBranch: string;
}

export interface MarkdownPublishResult {
  status: "published" | "up_to_date";
  path: string;
  commitSha: string | null;
  htmlUrl: string | null;
  publishedAt: string | null;
}

export interface AvailableGitHubRepository {
  githubRepositoryId: number;
  installationId: number;
  fullName: string;
  private: boolean;
}

export function getGitHubRepositories(): Promise<GitHubRepository[]> {
  return apiFetch<GitHubRepository[]>("/api/github/repositories");
}

export function getAvailableGitHubRepositories(): Promise<AvailableGitHubRepository[]> {
  return apiFetch<AvailableGitHubRepository[]>("/api/github/available-repositories");
}

export function connectGitHubRepository(repositoryId: number): Promise<GitHubRepository> {
  return apiFetch<GitHubRepository>("/api/github/repositories/connect", {
    method: "POST",
    body: JSON.stringify({ githubRepositoryId: repositoryId }),
  });
}

export function publishWorklog(
  worklogId: string,
  repositoryId: string,
  path: string,
  commitMessage: string,
): Promise<MarkdownPublishResult> {
  return apiFetch<MarkdownPublishResult>(`/api/worklogs/${encodeURIComponent(worklogId)}/publish`, {
    method: "POST",
    body: JSON.stringify({ repositoryId, path, commitMessage }),
  });
}
