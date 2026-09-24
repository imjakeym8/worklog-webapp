const DATE_ONLY_PATTERN = /^\d{4}-\d{2}-\d{2}$/;

/** Parse a valid YYYY-MM-DD date as local noon to avoid timezone day shifts. */
export function parseWorklogDate(value: string): Date | null {
  if (!DATE_ONLY_PATTERN.test(value)) return null;

  const [year, month, day] = value.split("-").map(Number);
  const date = new Date(year, month - 1, day, 12);

  if (
    date.getFullYear() !== year ||
    date.getMonth() !== month - 1 ||
    date.getDate() !== day
  ) {
    return null;
  }

  return date;
}

export function isValidWorklogDate(value: string): boolean {
  return parseWorklogDate(value) !== null;
}

export function formatWorklogDate(value: string): string {
  if (!value) return "Select a date";

  const date = parseWorklogDate(value);
  if (!date) return "Select a valid date";

  return new Intl.DateTimeFormat("en", {
    month: "long",
    day: "numeric",
    year: "numeric",
  }).format(date);
}

export function formatWorklogShortDate(value: string): string {
  const date = parseWorklogDate(value);
  if (!date) return "—";

  return new Intl.DateTimeFormat("en", {
    day: "2-digit",
    month: "short",
  }).format(date).toUpperCase();
}
