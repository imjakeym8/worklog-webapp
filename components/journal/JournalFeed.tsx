"use client";

import { useState } from "react";
import { formatWorklogMonth, formatWorklogShortDate } from "@/lib/dates";
import type { WorklogEntry } from "@/types";

interface JournalFeedProps {
  entries: WorklogEntry[];
  deletingWorklogId?: string | null;
  onDelete?: (worklog: WorklogEntry) => void;
  onEdit?: (worklog: WorklogEntry) => void;
  onPreviewAttachment?: (worklog: WorklogEntry, trigger: HTMLButtonElement) => void;
  onExportMarkdown?: (worklog: WorklogEntry) => void;
  onPublishMarkdown?: (worklog: WorklogEntry) => void;
  showFilteredEmptyState: boolean;
  readOnly?: boolean;
  emptyMessage?: string;
}

function PaperclipIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" width="14" height="14" fill="none">
      <path d="m8.5 12.5 5.9-5.9a3 3 0 1 1 4.2 4.2l-8.1 8.1a5 5 0 0 1-7.1-7.1l8.1-8.1" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function MarkdownNotes({ notes }: { notes: string }) {
  return (
    <div className="notes-content">
      {notes.split("\n\n").map((paragraph, index) => {
        if (paragraph.startsWith("```")) {
          return (
            <pre key={index}>
              <code>{paragraph.replace(/^```[a-z]*\n?|```$/g, "")}</code>
            </pre>
          );
        }

        if (paragraph.startsWith("- ")) {
          return (
            <ul key={index}>
              {paragraph.split("\n").map((item) => (
                <li key={item}>{item.slice(2)}</li>
              ))}
            </ul>
          );
        }

        return <p key={index}>{paragraph}</p>;
      })}
    </div>
  );
}

export function JournalFeed({
  entries,
  deletingWorklogId,
  onDelete,
  onEdit,
  onPreviewAttachment,
  onExportMarkdown,
  onPublishMarkdown,
  showFilteredEmptyState,
  readOnly = false,
  emptyMessage,
}: JournalFeedProps) {
  const [openNotes, setOpenNotes] = useState<string | null>(null);
  const groupedEntries = entries.reduce<Record<string, WorklogEntry[]>>(
    (groups, entry) => {
      const month = formatWorklogMonth(entry.date);
      groups[month] ??= [];
      groups[month].push(entry);
      return groups;
    },
    {},
  );

  if (!entries.length) {
    return (
      <div className="empty-state">
        {showFilteredEmptyState
          ? "No worklogs match these filters. Try another track or search term."
          : (emptyMessage ?? "No worklogs yet. Add a log to begin your journal.")}
      </div>
    );
  }

  return (
    <section aria-label="Worklog timeline" className="timeline">
      {Object.entries(groupedEntries).map(([month, monthEntries]) => (
        <div key={month} className="month-group">
          <h2>{month}</h2>
          {monthEntries.map((entry) => {
            const notesOpen = openNotes === entry.id;
            const isDeleting = deletingWorklogId === entry.id;

            return (
              <article id={entry.date} key={entry.id} className="worklog-card">
                <div className="date-column">
                  <time dateTime={entry.date}>{formatWorklogShortDate(entry.date)}</time>
                  <span className="hours">{entry.hours}h</span>
                </div>
                <div className="entry-content">
                  <div className="entry-topline">
                    <div className="track-list">
                      {entry.tracks.map((track) => (
                        <span key={track}>{track}</span>
                      ))}
                    </div>
                    <span className={entry.shipped ? "status shipped" : "status in-progress"}>
                      <i /> {entry.shipped ? "Shipped" : "In progress"}
                    </span>
                    {!readOnly && <span className={`visibility-badge ${entry.visibility}`}>{entry.visibility}</span>}
                  </div>
                  <p className="activity">{entry.activityBreakdown}</p>
                  {entry.blockers.length > 0 && (
                    <p className="metadata blockers">
                      <b>⚠</b> {entry.blockers.join(" · ")}
                    </p>
                  )}
                  {entry.next.length > 0 && (
                    <p className="metadata next">
                      <b>→</b> {entry.next.join(" · ")}
                    </p>
                  )}
                  {entry.quickSummary && (
                    <p className="summary">
                      <b>✦</b> {entry.quickSummary}
                    </p>
                  )}
                  {entry.attachment && onPreviewAttachment && (
                    <button
                      type="button"
                      className="attachment-link"
                      title={entry.attachment.originalFilename}
                      aria-label={`Preview image attachment ${entry.attachment.originalFilename}`}
                      onClick={(event) => onPreviewAttachment(entry, event.currentTarget)}
                    >
                      <PaperclipIcon />
                      <span>{entry.attachment.originalFilename}</span>
                    </button>
                  )}
                  <div className="entry-actions">
                    <div>
                      {entry.detailedNotes && (
                        <button
                          className="disclosure"
                          onClick={() => setOpenNotes(notesOpen ? null : entry.id)}
                          aria-expanded={notesOpen}
                        >
                          <span>{notesOpen ? "⌄" : "›"}</span> Detailed notes
                        </button>
                      )}
                    </div>
                    {!readOnly && onEdit && onExportMarkdown && onPublishMarkdown && onDelete && (
                    <div className="record-actions">
                      <button type="button" onClick={() => onEdit(entry)} disabled={isDeleting}>
                        Edit
                      </button>
                      <button type="button" onClick={() => onExportMarkdown(entry)}>
                        Export .md
                      </button>
                      <button type="button" onClick={() => onPublishMarkdown(entry)}>
                        Publish
                      </button>
                      <button
                        type="button"
                        className="delete-action"
                        onClick={() => onDelete(entry)}
                        disabled={isDeleting}
                      >
                        {isDeleting ? "Deleting…" : "Delete"}
                      </button>
                    </div>
                    )}
                  </div>
                  {notesOpen && (
                    <div className="expandable">
                      <MarkdownNotes notes={entry.detailedNotes} />
                    </div>
                  )}
                </div>
              </article>
            );
          })}
        </div>
      ))}
    </section>
  );
}
