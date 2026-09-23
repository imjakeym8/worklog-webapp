export interface GitHubEvent {
  id: string;
  type: "commit" | "pull_request";
  time: string;
  title: string;
  sha?: string;
  url?: string;
}

export interface GitHubActivity {
  repository: string;
  commits: number;
  pullRequests: number;
  events: GitHubEvent[];
}

export interface WorklogEntry {
  id: string;
  date: string;
  tracks: string[];
  hours: number;
  shipped: boolean;
  visibility: "public" | "private";
  blockers: string[];
  next: string[];
  activityBreakdown: string;
  detailedNotes: string;
  quickSummary: string;
  attachment: WorklogAttachment | null;
  createdAt: string;
  updatedAt: string;
}

export interface WorklogAttachment {
  id: string;
  worklogId: string;
  originalFilename: string;
  contentType: "image/jpeg" | "image/png";
  sizeBytes: number;
  width: number;
  height: number;
  createdAt: string;
}

export interface WorklogInput {
  date: string;
  tracks: string[];
  hours: number;
  shipped: boolean;
  visibility: "public" | "private";
  blockers: string[];
  next: string[];
  activityBreakdown: string;
  detailedNotes: string;
  quickSummary: string;
}

export type WorklogUpdateInput = Partial<WorklogInput>;

export interface CurrentUser {
  id: string;
  githubLogin: string;
  displayName: string | null;
  avatarUrl: string | null;
  isAdmin: boolean;
}
