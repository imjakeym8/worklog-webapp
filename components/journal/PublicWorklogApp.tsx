"use client";

import { useEffect, useMemo, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { JournalFeed } from "@/components/journal/JournalFeed";
import {
  getPublicProfile,
  getPublicWorklogAttachment,
  getPublicWorklogs,
  type PublicProfile,
} from "@/lib/api/public";
import type { WorklogEntry } from "@/types";

export function PublicWorklogApp() {
  const [entries, setEntries] = useState<WorklogEntry[]>([]);
  const [profile, setProfile] = useState<PublicProfile | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [year, setYear] = useState(String(new Date().getFullYear()));
  const [track, setTrack] = useState("All tracks");
  const [search, setSearch] = useState("");
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([getPublicWorklogs(), getPublicProfile()])
      .then(([worklogs, owner]) => {
        setEntries(worklogs);
        setProfile(owner);
      })
      .catch(() => setLoadError("Public worklogs could not be loaded."))
      .finally(() => setIsLoading(false));
  }, []);

  const years = useMemo(() => Array.from(new Set(entries.map((entry) => entry.date.slice(0, 4))).values()).sort().reverse(), [entries]);
  const tracks = useMemo(() => Array.from(new Set(entries.flatMap((entry) => entry.tracks))).sort(), [entries]);
  const filteredEntries = useMemo(() => {
    const term = search.trim().toLowerCase();
    return entries.filter((entry) => entry.date.startsWith(year) && (track === "All tracks" || entry.tracks.includes(track)) && (!term || [entry.activityBreakdown, entry.detailedNotes, entry.quickSummary, ...entry.tracks, ...entry.blockers, ...entry.next].join(" ").toLowerCase().includes(term)));
  }, [entries, search, track, year]);
  const hasActiveFilters = Boolean(search.trim()) || track !== "All tracks" || entries.some((entry) => !entry.date.startsWith(year));

  async function previewAttachment(entry: WorklogEntry): Promise<void> {
    try {
      const blob = await getPublicWorklogAttachment(entry.id);
      setPreviewUrl(URL.createObjectURL(blob));
    } catch {
      setLoadError("The public attachment could not be loaded.");
    }
  }

  return (
    <main className="app-shell">
      <div className="app-frame">
        <header className="app-header">
          <div><Link className="wordmark" href="/">worklog<span>.</span></Link><p>Building, learning, debugging, shipping.</p></div>
          {profile && <a className="public-profile" href={profile.githubProfileUrl} target="_blank" rel="noreferrer">{profile.githubAvatarUrl && <Image src={profile.githubAvatarUrl} alt="" width={32} height={32} />}<span>Connected GitHub<br /><b>@{profile.githubLogin}</b></span></a>}
        </header>
        <section className="controls public-controls" aria-label="Public Worklog filters">
          <label className="select-wrap"><span className="sr-only">Year</span><select value={year} onChange={(event) => setYear(event.target.value)}>{years.length === 0 && <option>{year}</option>}{years.map((option) => <option key={option}>{option}</option>)}</select></label>
          <label className="select-wrap track-select"><span className="sr-only">Track</span><select value={track} onChange={(event) => setTrack(event.target.value)}><option>All tracks</option>{tracks.map((option) => <option key={option}>{option}</option>)}</select></label>
          <label className="search"><span>⌕</span><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search public worklogs..." aria-label="Search public worklogs" /></label>
        </section>
        {loadError && <p className="api-message error" role="alert">{loadError}</p>}
        <div className="feed-caption"><span>Public timeline</span><span>{filteredEntries.length} {filteredEntries.length === 1 ? "entry" : "entries"}</span></div>
        {isLoading ? <div className="empty-state">Loading public worklogs…</div> : <JournalFeed entries={filteredEntries} showFilteredEmptyState={hasActiveFilters && filteredEntries.length === 0} readOnly emptyMessage="No public worklogs have been shared yet." onPreviewAttachment={(entry) => void previewAttachment(entry)} />}
      </div>
      {previewUrl && <div className="attachment-preview-backdrop" role="dialog" aria-modal="true"><div className="attachment-preview-dialog"><button className="close" onClick={() => { URL.revokeObjectURL(previewUrl); setPreviewUrl(null); }} aria-label="Close image preview">×</button><Image src={previewUrl} alt="Public Worklog attachment" width={1200} height={900} unoptimized /></div></div>}
    </main>
  );
}
