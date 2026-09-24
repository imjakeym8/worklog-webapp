"use client";

import {
  FormEvent,
  KeyboardEvent,
  useRef,
  useEffect,
  useMemo,
  useState,
} from "react";
import Link from "next/link";
import Image from "next/image";
import { JournalFeed } from "@/components/journal/JournalFeed";
import { GITHUB_ADMIN_LOGIN_URL, getCurrentUser, logout } from "@/lib/api/auth";
import { connectGitHubRepository, getAvailableGitHubRepositories, getGitHubRepositories, publishWorklog, type AvailableGitHubRepository, type GitHubRepository } from "@/lib/api/github";
import {
  createWorklog,
  createWorklogAttachment,
  deleteWorklogAttachment,
  deleteWorklog,
  getWorklogAttachmentPreview,
  getWorklogMarkdown,
  getWorklogs,
  importMarkdownWorklog,
  replaceWorklogAttachment,
  updateWorklog,
} from "@/lib/api/worklogs";
import { formatWorklogDate, isValidWorklogDate } from "@/lib/dates";
import type { CurrentUser, WorklogAttachment, WorklogEntry, WorklogInput } from "@/types";

interface WorklogDraft {
  date: string;
  activity: string;
  tracks: string;
  hours: string;
  shipped: boolean;
  visibility: "public" | "private";
  blockers: string;
  next: string;
  notes: string;
  summary: string;
}

function SettingsIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" preserveAspectRatio="xMidYMid meet">
      <g fill="currentColor">
        <circle cx="12" cy="12" r="7.5" />
        <rect x="10.25" y="1.5" width="3.5" height="5" rx="0.5" />
        <rect x="10.25" y="1.5" width="3.5" height="5" rx="0.5" transform="rotate(45 12 12)" />
        <rect x="10.25" y="1.5" width="3.5" height="5" rx="0.5" transform="rotate(90 12 12)" />
        <rect x="10.25" y="1.5" width="3.5" height="5" rx="0.5" transform="rotate(135 12 12)" />
        <rect x="10.25" y="1.5" width="3.5" height="5" rx="0.5" transform="rotate(180 12 12)" />
        <rect x="10.25" y="1.5" width="3.5" height="5" rx="0.5" transform="rotate(225 12 12)" />
        <rect x="10.25" y="1.5" width="3.5" height="5" rx="0.5" transform="rotate(270 12 12)" />
        <rect x="10.25" y="1.5" width="3.5" height="5" rx="0.5" transform="rotate(315 12 12)" />
      </g>
      <circle cx="12" cy="12" r="3" fill="var(--settings-button-bg)" />
    </svg>
  );
}

function today(): string {
  const now = new Date();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${now.getFullYear()}-${month}-${day}`;
}

function commaList(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function blankDraft(): WorklogDraft {
  return {
    date: today(),
    activity: "",
    tracks: "",
    hours: "",
    shipped: false,
    visibility: "private",
    blockers: "",
    next: "",
    notes: "",
    summary: "",
  };
}

function draftFromWorklog(worklog: WorklogEntry): WorklogDraft {
  return {
    date: worklog.date,
    activity: worklog.activityBreakdown,
    tracks: worklog.tracks.join(", "),
    hours: String(worklog.hours),
    shipped: worklog.shipped,
    visibility: worklog.visibility,
    blockers: worklog.blockers.join(", "),
    next: worklog.next.join(", "),
    notes: worklog.detailedNotes,
    summary: worklog.quickSummary,
  };
}

function worklogInputFromDraft(draft: WorklogDraft): WorklogInput {
  return {
    date: draft.date,
    tracks: commaList(draft.tracks),
    hours: Number(draft.hours),
    shipped: draft.shipped,
    visibility: draft.visibility,
    blockers: commaList(draft.blockers),
    next: commaList(draft.next),
    activityBreakdown: draft.activity,
    detailedNotes: draft.notes,
    quickSummary: draft.summary,
  };
}

function sortWorklogs(worklogs: WorklogEntry[]): WorklogEntry[] {
  return [...worklogs].sort((left, right) => {
    const dateOrder = right.date.localeCompare(left.date);
    if (dateOrder !== 0) {
      return dateOrder;
    }

    const createdAtOrder = right.createdAt.localeCompare(left.createdAt);
    if (createdAtOrder !== 0) {
      return createdAtOrder;
    }

    return right.id.localeCompare(left.id);
  });
}

function isSupportedAttachment(file: File): boolean {
  return (
    (file.type === "image/jpeg" || file.type === "image/png") &&
    file.size > 0 &&
    file.size <= 5 * 1024 * 1024
  );
}

interface AttachmentPreview {
  attachment: WorklogAttachment;
  objectUrl: string;
}

export function WorklogApp() {
  const [currentUser, setCurrentUser] = useState<CurrentUser | null | undefined>(undefined);
  const [authError, setAuthError] = useState<string | null>(null);
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const [entries, setEntries] = useState<WorklogEntry[]>([]);
  const [composerOpen, setComposerOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [year, setYear] = useState(today().slice(0, 4));
  const [track, setTrack] = useState("All tracks");
  const [search, setSearch] = useState("");
  const [draft, setDraft] = useState<WorklogDraft>(blankDraft);
  const [editingWorklogId, setEditingWorklogId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [deletingWorklogId, setDeletingWorklogId] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [mutationError, setMutationError] = useState<string | null>(null);
  const [selectedAttachment, setSelectedAttachment] = useState<File | null>(null);
  const [isAttachmentMutating, setIsAttachmentMutating] = useState(false);
  const [attachmentPreview, setAttachmentPreview] = useState<AttachmentPreview | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [importOpen, setImportOpen] = useState(false);
  const [markdownFile, setMarkdownFile] = useState<File | null>(null);
  const [markdownImportError, setMarkdownImportError] = useState<string | null>(null);
  const [isImportingMarkdown, setIsImportingMarkdown] = useState(false);
  const [publishWorklogEntry, setPublishWorklogEntry] = useState<WorklogEntry | null>(null);
  const [githubRepositories, setGithubRepositories] = useState<GitHubRepository[]>([]);
  const [selectedRepositoryId, setSelectedRepositoryId] = useState("");
  const [publishPath, setPublishPath] = useState("");
  const [commitMessage, setCommitMessage] = useState("");
  const [markdownPreview, setMarkdownPreview] = useState("");
  const [publishError, setPublishError] = useState<string | null>(null);
  const [isPublishing, setIsPublishing] = useState(false);
  const [availableGitHubRepositories, setAvailableGitHubRepositories] = useState<AvailableGitHubRepository[]>([]);
  const [selectedAvailableRepositoryId, setSelectedAvailableRepositoryId] = useState("");
  const [isConnectingRepository, setIsConnectingRepository] = useState(false);
  const previewTriggerRef = useRef<HTMLButtonElement | null>(null);

  async function loadWorklogs(): Promise<void> {
    setIsLoading(true);
    setLoadError(null);

    try {
      setEntries(sortWorklogs(await getWorklogs()));
    } catch {
      setLoadError("Could not load worklogs. Check that the FastAPI backend is running.");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    let cancelled = false;

    const authenticationFailed =
      new URLSearchParams(window.location.search).get("auth") === "failed";

    getCurrentUser()
      .then((user) => {
        if (!cancelled) {
          if (authenticationFailed) {
            setAuthError("GitHub sign-in did not complete. Please try again.");
          }
          setCurrentUser(user);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setAuthError("Could not check your session. Check that FastAPI is running.");
          setCurrentUser(null);
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    if (!currentUser?.isAdmin) {
      return;
    }

    getWorklogs()
      .then((loadedWorklogs) => {
        if (!cancelled) {
          setEntries(sortWorklogs(loadedWorklogs));
        }
      })
      .catch(() => {
        if (!cancelled) {
          setLoadError("Could not load worklogs. Check that the FastAPI backend is running.");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setIsLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [currentUser]);

  const tracks = useMemo(() => {
    const availableTracks = new Set(entries.flatMap((entry) => entry.tracks));
    if (track !== "All tracks") {
      availableTracks.add(track);
    }
    return Array.from(availableTracks).sort();
  }, [entries, track]);

  const years = useMemo(() => {
    const availableYears = new Set(entries.map((entry) => entry.date.slice(0, 4)));
    availableYears.add(year);
    return Array.from(availableYears).sort().reverse();
  }, [entries, year]);

  const filteredEntries = useMemo(() => {
    const term = search.toLowerCase().trim();

    return entries.filter((entry) => {
      const searchableText = [
        entry.activityBreakdown,
        entry.detailedNotes,
        entry.quickSummary,
        ...entry.tracks,
        ...entry.blockers,
        ...entry.next,
      ]
        .join(" ")
        .toLowerCase();

      return (
        entry.date.startsWith(year) &&
        (track === "All tracks" || entry.tracks.includes(track)) &&
        (!term || searchableText.includes(term))
      );
    });
  }, [entries, year, track, search]);

  // Only show the filtered-empty message when the user has narrowed the timeline.
  const hasActiveFilters =
    search.trim().length > 0 ||
    track !== "All tracks" ||
    entries.some((entry) => !entry.date.startsWith(year));
  const showFilteredEmptyState = hasActiveFilters && filteredEntries.length === 0;

  useEffect(() => {
    const params = new URLSearchParams();
    if (year) {
      params.set("year", year);
    }
    if (track !== "All tracks") {
      params.set("track", track);
    }
    if (search) {
      params.set("q", search);
    }
    window.history.replaceState(null, "", `${window.location.pathname}?${params.toString()}`);
  }, [year, track, search]);

  function openNewComposer(): void {
    setEditingWorklogId(null);
    setDraft(blankDraft());
    setMutationError(null);
    setSelectedAttachment(null);
    setComposerOpen(true);
  }

  function openEditComposer(worklog: WorklogEntry): void {
    setEditingWorklogId(worklog.id);
    setDraft(draftFromWorklog(worklog));
    setMutationError(null);
    setSelectedAttachment(null);
    setComposerOpen(true);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function closeComposer(): void {
    if (isSaving || isAttachmentMutating) {
      return;
    }
    setComposerOpen(false);
    setEditingWorklogId(null);
    setMutationError(null);
    setSelectedAttachment(null);
  }

  async function saveWorklog(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (
      isSaving ||
      !isValidWorklogDate(draft.date) ||
      !draft.activity.trim() ||
      !draft.hours ||
      Number(draft.hours) <= 0
    ) {
      return;
    }

    setIsSaving(true);
    setMutationError(null);
    const attachmentToUpload = selectedAttachment;

    try {
      const worklogInput = worklogInputFromDraft(draft);
      const savedWorklog = editingWorklogId
        ? await updateWorklog(editingWorklogId, worklogInput)
        : await createWorklog(worklogInput);

      // Use the server response so generated identifiers and timestamps remain authoritative.
      let worklogWithAttachment = savedWorklog;
      if (attachmentToUpload) {
        try {
          const attachment = savedWorklog.attachment
            ? await replaceWorklogAttachment(savedWorklog.id, attachmentToUpload)
            : await createWorklogAttachment(savedWorklog.id, attachmentToUpload);
          worklogWithAttachment = { ...savedWorklog, attachment };
        } catch {
          setEntries((currentEntries) =>
            sortWorklogs(
              editingWorklogId
                ? currentEntries.map((entry) =>
                    entry.id === savedWorklog.id ? savedWorklog : entry,
                  )
                : [savedWorklog, ...currentEntries],
            ),
          );
          setEditingWorklogId(savedWorklog.id);
          setMutationError(
            "Worklog saved, but the image could not be attached. Your journal entry is safe. Retry the image upload.",
          );
          return;
        }
      }

      setEntries((currentEntries) =>
        sortWorklogs(
          editingWorklogId
            ? currentEntries.map((entry) =>
                entry.id === worklogWithAttachment.id ? worklogWithAttachment : entry,
              )
            : [worklogWithAttachment, ...currentEntries],
        ),
      );
      setYear(savedWorklog.date.slice(0, 4));
      setTrack("All tracks");
      setSearch("");
      setDraft(blankDraft());
      setSelectedAttachment(null);
      setEditingWorklogId(null);
      setComposerOpen(false);
    } catch {
      // Preserve the composer draft when FastAPI rejects or cannot receive the request.
      setMutationError(
        editingWorklogId
          ? "Could not update worklog. Your edits have been preserved."
          : "Could not save worklog. Your entry has been preserved.",
      );
    } finally {
      setIsSaving(false);
    }
  }

  function selectAttachment(file: File | undefined): void {
    if (!file) {
      return;
    }
    if (!isSupportedAttachment(file)) {
      setSelectedAttachment(null);
      setMutationError("Choose a JPEG or PNG image that is no larger than 5 MB.");
      return;
    }
    setMutationError(null);
    setSelectedAttachment(file);
  }

  async function removeAttachment(worklog: WorklogEntry): Promise<void> {
    if (isAttachmentMutating || !worklog.attachment) {
      return;
    }
    setIsAttachmentMutating(true);
    setMutationError(null);
    try {
      await deleteWorklogAttachment(worklog.id);
      setEntries((currentEntries) =>
        currentEntries.map((entry) =>
          entry.id === worklog.id ? { ...entry, attachment: null } : entry,
        ),
      );
    } catch {
      setMutationError("Could not remove the image. It is still attached to this worklog.");
    } finally {
      setIsAttachmentMutating(false);
    }
  }

  async function previewAttachment(
    worklog: WorklogEntry,
    trigger: HTMLButtonElement,
  ): Promise<void> {
    if (!worklog.attachment) {
      return;
    }
    previewTriggerRef.current = trigger;
    setPreviewError(null);
    try {
      const image = await getWorklogAttachmentPreview(worklog.id);
      setAttachmentPreview({
        attachment: worklog.attachment,
        objectUrl: URL.createObjectURL(image),
      });
    } catch {
      setPreviewError("Could not load this private image attachment.");
    }
  }

  function closeAttachmentPreview(): void {
    setAttachmentPreview((currentPreview) => {
      if (currentPreview) {
        URL.revokeObjectURL(currentPreview.objectUrl);
      }
      return null;
    });
    window.setTimeout(() => previewTriggerRef.current?.focus(), 0);
  }

  useEffect(() => {
    function closeOnEscape(event: globalThis.KeyboardEvent): void {
      if (event.key === "Escape" && attachmentPreview) {
        closeAttachmentPreview();
      }
    }
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [attachmentPreview]);

  async function removeWorklog(worklog: WorklogEntry): Promise<void> {
    if (
      deletingWorklogId ||
      !window.confirm("Delete this worklog permanently? This action cannot be undone.")
    ) {
      return;
    }

    setDeletingWorklogId(worklog.id);
    setMutationError(null);

    try {
      await deleteWorklog(worklog.id);
      setEntries((currentEntries) =>
        currentEntries.filter((entry) => entry.id !== worklog.id),
      );
      if (editingWorklogId === worklog.id) {
        closeComposer();
      }
    } catch {
      setMutationError("Could not delete worklog. The entry has not been removed.");
    } finally {
      setDeletingWorklogId(null);
    }
  }

  async function importMarkdown(update = false): Promise<void> {
    if (!markdownFile || isImportingMarkdown) return;
    setIsImportingMarkdown(true);
    setMarkdownImportError(null);
    try {
      const imported = await importMarkdownWorklog(markdownFile, update);
      setEntries((current) =>
        sortWorklogs([imported, ...current.filter((item) => item.id !== imported.id)]),
      );
      setImportOpen(false);
      setMarkdownFile(null);
    } catch (error) {
      if (error instanceof Error && "code" in error && error.code === "MARKDOWN_IMPORT_CONFLICT") {
        setMarkdownImportError("This file has changed since its last import. Confirm to update it.");
      } else if (error instanceof Error) {
        setMarkdownImportError(error.message);
      } else {
        setMarkdownImportError("Could not import this Markdown file.");
      }
    } finally {
      setIsImportingMarkdown(false);
    }
  }

  async function exportMarkdown(worklog: WorklogEntry): Promise<void> {
    try {
      const blob = await getWorklogMarkdown(worklog.id);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `worklog-${worklog.date}.md`;
      link.click();
      URL.revokeObjectURL(url);
    } catch {
      setMutationError("Could not export this worklog as Markdown.");
    }
  }

  async function openPublishDialog(worklog: WorklogEntry): Promise<void> {
    setPublishWorklogEntry(worklog);
    setPublishPath(`journals/${worklog.date}.md`);
    setCommitMessage(`Add worklog for ${worklog.date}`);
    setPublishError(null);
    try {
      const [repositories, markdown] = await Promise.all([
        getGitHubRepositories(),
        getWorklogMarkdown(worklog.id),
      ]);
      setGithubRepositories(repositories);
      setSelectedRepositoryId(repositories[0]?.id ?? "");
      setMarkdownPreview(await markdown.text());
    } catch {
      setPublishError("Could not load the connected repositories or Markdown preview.");
    }
  }

  async function loadAvailableRepositories(): Promise<void> {
    try {
      const repositories = await getAvailableGitHubRepositories();
      setAvailableGitHubRepositories(repositories);
      setSelectedAvailableRepositoryId(String(repositories[0]?.githubRepositoryId ?? ""));
    } catch {
      setAuthError("Could not load repositories available through your GitHub App.");
    }
  }

  async function connectSelectedRepository(): Promise<void> {
    const repositoryId = Number(selectedAvailableRepositoryId);
    if (!repositoryId || isConnectingRepository) return;
    setIsConnectingRepository(true);
    try {
      await connectGitHubRepository(repositoryId);
      await loadAvailableRepositories();
    } catch {
      setAuthError("Could not connect that GitHub repository.");
    } finally {
      setIsConnectingRepository(false);
    }
  }

  async function publishMarkdown(): Promise<void> {
    if (!publishWorklogEntry || !selectedRepositoryId || isPublishing) return;
    setIsPublishing(true);
    setPublishError(null);
    try {
      const result = await publishWorklog(publishWorklogEntry.id, selectedRepositoryId, publishPath, commitMessage);
      setPublishError(result.status === "up_to_date" ? "Already up to date." : `Published ${result.path}.`);
    } catch (error) {
      setPublishError(error instanceof Error ? error.message : "Could not publish this Worklog.");
    } finally {
      setIsPublishing(false);
    }
  }

  function onComposerKeyDown(event: KeyboardEvent<HTMLFormElement>): void {
    if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
      event.preventDefault();
      if (!isSaving) {
        event.currentTarget.requestSubmit();
      }
    }
    if (event.key === "Escape") {
      closeComposer();
    }
  }

  async function signOut(): Promise<void> {
    if (isLoggingOut) {
      return;
    }
    setIsLoggingOut(true);
    setAuthError(null);
    try {
      await logout();
      setCurrentUser(null);
      setEntries([]);
      setSettingsOpen(false);
      setComposerOpen(false);
    } catch {
      setAuthError("Could not sign out. Please try again.");
    } finally {
      setIsLoggingOut(false);
    }
  }

  const isEditing = editingWorklogId !== null;
  const editingAttachment = isEditing
    ? entries.find((entry) => entry.id === editingWorklogId)?.attachment ?? null
    : null;

  if (currentUser === undefined) {
    return (
      <main className="auth-shell">
        <section className="auth-card" role="status">
          <Link className="wordmark" href="/">
            worklog<span>.</span>
          </Link>
          <p>Checking your session…</p>
        </section>
      </main>
    );
  }

  if (currentUser === null) {
    return (
      <main className="auth-shell">
        <section className="auth-card">
          <Link className="wordmark" href="/">
            worklog<span>.</span>
          </Link>
          <h1>A compact developer journal.</h1>
          <p>Capture what you built, learned, debugged, and shipped.</p>
          {authError && (
            <p className="api-message error" role="alert">
              {authError}
            </p>
          )}
          <a className="github-sign-in" href={GITHUB_ADMIN_LOGIN_URL}>
            Sign in with GitHub
          </a>
        </section>
      </main>
    );
  }

  if (!currentUser.isAdmin) {
    return (
      <main className="auth-shell">
        <section className="auth-card">
              <Link className="wordmark" href="/">worklog<span>.</span></Link>
          <h1>Access denied</h1>
          <p>This GitHub account is not authorized to manage this Worklog.</p>
          <button className="github-sign-in" type="button" onClick={() => void signOut()}>Sign out</button>
        </section>
      </main>
    );
  }

  return (
    <main className="app-shell">
      <div className="app-frame">
        <header className="app-header">
          <div>
            <Link className="wordmark" href="/">
              worklog<span>.</span>
            </Link>
            <p>Building, learning, debugging, shipping.</p>
          </div>
          <div className="header-actions">
            <button
              className="github-connection"
              title={`Signed in as @${currentUser.githubLogin}`}
              onClick={() => { setSettingsOpen(true); void loadAvailableRepositories(); }}
            >
              <span /> @{currentUser.githubLogin}
            </button>
            <button
              className="icon-button"
              onClick={() => { setSettingsOpen(true); void loadAvailableRepositories(); }}
              aria-label="Open settings"
            >
              <SettingsIcon />
            </button>
          </div>
        </header>

        <section className="controls" aria-label="Worklog filters">
          <label className="select-wrap">
            <span className="sr-only">Year</span>
            <select value={year} onChange={(event) => setYear(event.target.value)}>
              {years.map((option) => (
                <option key={option}>{option}</option>
              ))}
            </select>
          </label>
          <label className="select-wrap track-select">
            <span className="sr-only">Track</span>
            <select value={track} onChange={(event) => setTrack(event.target.value)}>
              <option>All tracks</option>
              {tracks.map((option) => (
                <option key={option}>{option}</option>
              ))}
            </select>
          </label>
          <label className="search">
            <span>⌕</span>
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search worklogs..."
              aria-label="Search worklogs"
            />
          </label>
          <button className="new-log" onClick={openNewComposer}>
            <span>+</span> Log
          </button>
        </section>

        {composerOpen && (
          <section className="composer-region">
            <form
              className="composer"
              onSubmit={(event) => void saveWorklog(event)}
              onKeyDown={onComposerKeyDown}
            >
              <div className="composer-heading">
                <div>
                  <span className="eyebrow">
                    {isEditing ? "Edit worklog" : "New worklog"}
                  </span>
                  <h1>{formatWorklogDate(draft.date)}</h1>
                </div>
                <button
                  type="button"
                  className="close"
                  onClick={closeComposer}
                  aria-label="Close composer"
                  disabled={isSaving}
                >
                  ×
                </button>
              </div>

              <div className="field">
                <label htmlFor="activity">
                  What did you work on? <em>*</em>
                </label>
                <textarea
                  id="activity"
                  value={draft.activity}
                  onChange={(event) => setDraft({ ...draft, activity: event.target.value })}
                  placeholder="A concise account of the work you did..."
                  required
                />
              </div>

              <div className="form-grid">
                <div className="field">
                  <label htmlFor="date">Date</label>
                  <input
                    id="date"
                    type="date"
                    value={draft.date}
                    onChange={(event) => setDraft({ ...draft, date: event.target.value })}
                    required
                    aria-describedby="date-help"
                    aria-invalid={!isValidWorklogDate(draft.date)}
                  />
                  <span id="date-help" className="field-message" role="status">
                    {!isValidWorklogDate(draft.date)
                      ? draft.date
                        ? "Enter a valid date to save this worklog."
                        : "Choose a date to save this worklog."
                      : ""}
                  </span>
                </div>
                <div className="field">
                  <label htmlFor="tracks">Tracks</label>
                  <input
                    id="tracks"
                    value={draft.tracks}
                    onChange={(event) => setDraft({ ...draft, tracks: event.target.value })}
                    placeholder="FastAPI, PostgreSQL"
                  />
                </div>
                <div className="field small-field">
                  <label htmlFor="hours">
                    Hours <em>*</em>
                  </label>
                  <input
                    id="hours"
                    type="number"
                    min="0.25"
                    step="0.25"
                    value={draft.hours}
                    onChange={(event) => setDraft({ ...draft, hours: event.target.value })}
                    placeholder="6"
                    required
                  />
                </div>
                <div className="field shipped-field">
                  <label htmlFor="shipped">Shipped</label>
                  <label className="shipped-toggle">
                    <input
                      id="shipped"
                      type="checkbox"
                      checked={draft.shipped}
                      onChange={(event) =>
                        setDraft({ ...draft, shipped: event.target.checked })
                      }
                    />
                    <span />
                  </label>
                </div>
                <div className="field">
                  <label htmlFor="visibility">Visibility</label>
                  <select
                    id="visibility"
                    value={draft.visibility}
                    onChange={(event) => setDraft({ ...draft, visibility: event.target.value as "public" | "private" })}
                  >
                    <option value="private">Private</option>
                    <option value="public">Public</option>
                  </select>
                </div>
              </div>

              <div className="form-grid lower">
                <div className="field">
                  <label htmlFor="blockers">Blockers</label>
                  <input
                    id="blockers"
                    value={draft.blockers}
                    onChange={(event) => setDraft({ ...draft, blockers: event.target.value })}
                    placeholder="Configuration, logging"
                  />
                </div>
                <div className="field">
                  <label htmlFor="next">Next</label>
                  <input
                    id="next"
                    value={draft.next}
                    onChange={(event) => setDraft({ ...draft, next: event.target.value })}
                    placeholder="Deployment, testing"
                  />
                </div>
              </div>

              <div className="field">
                <label htmlFor="notes">
                  Detailed notes <small>Markdown supported</small>
                </label>
                <textarea
                  id="notes"
                  className="notes-input"
                  value={draft.notes}
                  onChange={(event) => setDraft({ ...draft, notes: event.target.value })}
                  placeholder="Technical notes, commands, decisions…"
                />
              </div>
              <div className="field">
                <label htmlFor="summary">Quick summary</label>
                <textarea
                  id="summary"
                  value={draft.summary}
                  onChange={(event) => setDraft({ ...draft, summary: event.target.value })}
                  placeholder="What did you learn or struggle with?"
                />
              </div>

              <div className="field attachment-field">
                <label htmlFor="attachment">Image attachment <small>JPEG or PNG, up to 5 MB</small></label>
                {editingAttachment && !selectedAttachment && (
                  <div className="attachment-current">
                    <span>{editingAttachment.originalFilename}</span>
                    <div>
                      <button
                        type="button"
                        onClick={() => document.getElementById("attachment")?.click()}
                        disabled={isAttachmentMutating || isSaving}
                      >
                        Replace
                      </button>
                      <button
                        type="button"
                        className="delete-action"
                        onClick={() => {
                          const entry = entries.find((item) => item.id === editingWorklogId);
                          if (entry) {
                            void removeAttachment(entry);
                          }
                        }}
                        disabled={isAttachmentMutating || isSaving}
                      >
                        {isAttachmentMutating ? "Removing…" : "Remove"}
                      </button>
                    </div>
                  </div>
                )}
                <input
                  id="attachment"
                  type="file"
                  accept="image/jpeg,image/png"
                  onChange={(event) => selectAttachment(event.target.files?.[0])}
                  disabled={isSaving || isAttachmentMutating}
                />
                {selectedAttachment && (
                  <div className="attachment-confirmation" role="status">
                    <span>
                      {selectedAttachment.name} will be {editingAttachment ? "replaced" : "attached"} when you save.
                    </span>
                    <button type="button" onClick={() => setSelectedAttachment(null)} disabled={isSaving}>
                      Cancel image
                    </button>
                  </div>
                )}
              </div>

              {mutationError && (
                <p className="api-message error" role="alert">
                  {mutationError}
                </p>
              )}

              <div className="composer-footer">
                <button
                  type="button"
                  className="import-log"
                  onClick={() => setImportOpen(true)}
                  disabled={isSaving || isAttachmentMutating}
                >
                  Import .md
                </button>
                <div>
                  <button
                    type="button"
                    className="cancel"
                    onClick={closeComposer}
                    disabled={isSaving}
                  >
                    Cancel
                  </button>
                  <button className="save" type="submit" disabled={isSaving || isAttachmentMutating}>
                    {isSaving ? "Saving…" : isEditing ? "Save changes" : "Save worklog"}
                  </button>
                </div>
              </div>
            </form>
          </section>
        )}

        {loadError && (
          <div className="api-message error" role="alert">
            <span>{loadError}</span>
            <button type="button" onClick={() => void loadWorklogs()} disabled={isLoading}>
              {isLoading ? "Retrying…" : "Retry"}
            </button>
          </div>
        )}
        {mutationError && !composerOpen && (
          <p className="api-message error" role="alert">
            {mutationError}
          </p>
        )}

        <div className="feed-caption">
          <span>Timeline</span>
          <span>
            {filteredEntries.length} {filteredEntries.length === 1 ? "entry" : "entries"}
          </span>
        </div>

        {isLoading && entries.length === 0 ? (
          <div className="empty-state" role="status">
            Loading worklogs…
          </div>
        ) : loadError && entries.length === 0 ? null : (
          <JournalFeed
            entries={filteredEntries}
            deletingWorklogId={deletingWorklogId}
            onDelete={(worklog) => void removeWorklog(worklog)}
            onEdit={openEditComposer}
            onPreviewAttachment={(worklog, trigger) => void previewAttachment(worklog, trigger)}
            onExportMarkdown={(worklog) => void exportMarkdown(worklog)}
            onPublishMarkdown={(worklog) => void openPublishDialog(worklog)}
            showFilteredEmptyState={showFilteredEmptyState}
          />
        )}
      </div>

      {settingsOpen && (
        <div className="dialog-backdrop" onMouseDown={() => setSettingsOpen(false)}>
          <section
            className="settings-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="settings-title"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <button
              className="close"
              onClick={() => setSettingsOpen(false)}
              aria-label="Close settings"
            >
              ×
            </button>
            <span className="eyebrow">Preferences</span>
            <h2 id="settings-title">Your workspace</h2>
            <div className="connected-account">
              <span className="avatar">
                {currentUser.githubLogin.slice(0, 1).toUpperCase()}
              </span>
              <div>
                <b>{currentUser.displayName || currentUser.githubLogin}</b>
                <small>Signed in as @{currentUser.githubLogin}</small>
              </div>
              <button type="button" onClick={() => void signOut()} disabled={isLoggingOut}>
                {isLoggingOut ? "Signing out…" : "Sign out"}
              </button>
            </div>
            <div className="field">
              <label htmlFor="github-repository">GitHub repository</label>
              <select id="github-repository" value={selectedAvailableRepositoryId} onChange={(event) => setSelectedAvailableRepositoryId(event.target.value)}>
                {availableGitHubRepositories.length === 0 ? <option value="">No App repositories available</option> : availableGitHubRepositories.map((repository) => <option key={repository.githubRepositoryId} value={repository.githubRepositoryId}>{repository.fullName}</option>)}
              </select>
              <button className="repository-connect" type="button" onClick={() => void connectSelectedRepository()} disabled={!selectedAvailableRepositoryId || isConnectingRepository}>{isConnectingRepository ? "Connecting…" : "Connect repository"}</button>
            </div>
            {authError && (
              <p className="api-message error" role="alert">
                {authError}
              </p>
            )}
          </section>
        </div>
      )}
      {importOpen && (
        <div className="dialog-backdrop" onMouseDown={() => !isImportingMarkdown && setImportOpen(false)}>
          <section className="settings-dialog import-dialog" role="dialog" aria-modal="true" aria-labelledby="import-title" onMouseDown={(event) => event.stopPropagation()}>
            <button className="close" type="button" aria-label="Close Markdown import" onClick={() => setImportOpen(false)} disabled={isImportingMarkdown}>×</button>
            <span className="eyebrow">Portability</span>
            <h2 id="import-title">Import Worklog</h2>
            <p className="settings-note">Choose one Markdown worklog. It will be validated before it is added to your journal.</p>
            <div className="field">
              <label htmlFor="markdown-import">Markdown file <small>.md, up to 1 MB</small></label>
              <input id="markdown-import" type="file" accept=".md,text/markdown" onChange={(event) => { setMarkdownFile(event.target.files?.[0] ?? null); setMarkdownImportError(null); }} disabled={isImportingMarkdown} />
            </div>
            {markdownFile && <p className="import-file">{markdownFile.name}</p>}
            {markdownImportError && <p className="api-message error" role="alert">{markdownImportError}</p>}
            <div className="composer-footer import-actions">
              <button className="cancel" type="button" onClick={() => setImportOpen(false)} disabled={isImportingMarkdown}>Cancel</button>
              <button className="save" type="button" onClick={() => void importMarkdown(markdownImportError?.startsWith("This file has changed") === true)} disabled={!markdownFile || isImportingMarkdown}>
                {isImportingMarkdown ? "Importing…" : markdownImportError?.startsWith("This file has changed") ? "Update existing" : "Import Worklog"}
              </button>
            </div>
          </section>
        </div>
      )}
      {publishWorklogEntry && (
        <div className="dialog-backdrop" onMouseDown={() => !isPublishing && setPublishWorklogEntry(null)}>
          <section className="settings-dialog import-dialog" role="dialog" aria-modal="true" aria-labelledby="publish-title" onMouseDown={(event) => event.stopPropagation()}>
            <button className="close" type="button" aria-label="Close GitHub publish" onClick={() => setPublishWorklogEntry(null)} disabled={isPublishing}>×</button>
            <span className="eyebrow">GitHub</span>
            <h2 id="publish-title">Publish Worklog</h2>
            <div className="field"><label htmlFor="publish-repository">Repository</label><select id="publish-repository" value={selectedRepositoryId} onChange={(event) => setSelectedRepositoryId(event.target.value)}>{githubRepositories.length === 0 ? <option value="">No connected repositories</option> : githubRepositories.map((repository) => <option key={repository.id} value={repository.id}>{repository.fullName}</option>)}</select></div>
            <div className="field"><label htmlFor="publish-path">Path</label><input id="publish-path" value={publishPath} onChange={(event) => setPublishPath(event.target.value)} /></div>
            <div className="field"><label htmlFor="publish-message">Commit message</label><input id="publish-message" value={commitMessage} onChange={(event) => setCommitMessage(event.target.value)} /></div>
            <div className="field"><label htmlFor="markdown-preview">Markdown preview</label><textarea id="markdown-preview" className="notes-input" value={markdownPreview} readOnly /></div>
            {publishError && <p className="api-message error" role="status">{publishError}</p>}
            <div className="composer-footer import-actions"><button className="cancel" type="button" onClick={() => setPublishWorklogEntry(null)} disabled={isPublishing}>Cancel</button><button className="save" type="button" onClick={() => void publishMarkdown()} disabled={!selectedRepositoryId || !publishPath || !commitMessage || isPublishing}>{isPublishing ? "Publishing…" : "Publish to GitHub"}</button></div>
          </section>
        </div>
      )}
      {attachmentPreview && (
        <div className="dialog-backdrop attachment-preview-backdrop" onMouseDown={closeAttachmentPreview}>
          <section
            className="attachment-preview-dialog"
            role="dialog"
            aria-modal="true"
            aria-label={`Image attachment: ${attachmentPreview.attachment.originalFilename}`}
            onMouseDown={(event) => event.stopPropagation()}
          >
            <button className="close" type="button" onClick={closeAttachmentPreview} aria-label="Close image preview">
              ×
            </button>
            <Image
              src={attachmentPreview.objectUrl}
              alt={attachmentPreview.attachment.originalFilename}
              width={attachmentPreview.attachment.width}
              height={attachmentPreview.attachment.height}
              unoptimized
            />
            <p>{attachmentPreview.attachment.originalFilename}</p>
          </section>
        </div>
      )}
      {previewError && (
        <p className="api-message error attachment-preview-error" role="alert">
          {previewError}
        </p>
      )}
    </main>
  );
}
