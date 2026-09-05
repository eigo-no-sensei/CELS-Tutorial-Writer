import type { TutorialType } from "./types";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"] as const;

interface DateParts {
  day: number;
  month: number;
  year: number | null;
}

function dateParts(value: string | null): DateParts | null {
  if (!value) return null;
  const trimmed = value.trim();
  let match = /^(\d{4})-(\d{2})-(\d{2})/.exec(trimmed);
  if (match) {
    return { year: Number(match[1]), month: Number(match[2]), day: Number(match[3]) };
  }
  match = /^(\d{2})-(\d{2})-(\d{4})/.exec(trimmed);
  if (match) {
    return { year: Number(match[3]), month: Number(match[2]), day: Number(match[1]) };
  }
  match = /^(\d{2})\/(\d{2})\/(\d{4})/.exec(trimmed);
  if (match) {
    return { year: Number(match[3]), month: Number(match[2]), day: Number(match[1]) };
  }
  return null;
}

function displayDate(parts: DateParts | null, withYear: boolean): string {
  if (!parts || parts.month < 1 || parts.month > 12 || parts.day < 1 || parts.day > 31) return "—";
  const base = `${String(parts.day).padStart(2, "0")} ${MONTHS[parts.month - 1]}`;
  return withYear && parts.year ? `${base} ${parts.year}` : base;
}

export function formatCourseRange(start: string | null, end: string | null): string {
  const startParts = dateParts(start);
  const endParts = dateParts(end);
  if (!startParts && !endParts) return "—";
  const spansYears = Boolean(startParts?.year && endParts?.year && startParts.year !== endParts.year);
  if (!startParts) return `Until ${displayDate(endParts, true)}`;
  if (!endParts) return `From ${displayDate(startParts, true)}`;
  return `${displayDate(startParts, spansYears)} – ${displayDate(endParts, spansYears)}`;
}

export function formatAttendance(value: number | null): string {
  return value == null ? "—" : `${value}%`;
}

export function formatTutorialType(value: TutorialType | null): string {
  if (!value) return "";
  return value.charAt(0).toUpperCase() + value.slice(1);
}

export function formatLastTutorial(date: string | null, type: TutorialType | null): string {
  if (!date && !type) return "—";
  const formattedDate = displayDate(dateParts(date), false);
  const formattedType = formatTutorialType(type);
  if (formattedDate === "—") return formattedType || "—";
  return formattedType ? `${formattedDate} · ${formattedType}` : formattedDate;
}
