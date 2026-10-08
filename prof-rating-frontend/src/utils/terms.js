// NUS academic calendar. Mirrors backend/terms.py: academic years start in August.

export const SEMESTERS = [
  { value: 1, label: 'Semester 1', short: 'Sem 1' },
  { value: 2, label: 'Semester 2', short: 'Sem 2' },
  { value: 3, label: 'Special Term 1', short: 'ST1' },
  { value: 4, label: 'Special Term 2', short: 'ST2' },
];

/** Start year of the current academic year: Oct 2026 -> 2026 (AY26/27). */
export function currentAcademicYear(today = new Date()) {
  return today.getMonth() >= 7 ? today.getFullYear() : today.getFullYear() - 1;
}

/** 2025 -> "AY25/26" */
export function formatAcademicYear(startYear) {
  const yy = (n) => String(n % 100).padStart(2, '0');
  return `AY${yy(startYear)}/${yy(startYear + 1)}`;
}

/** Newest first, back `count` years: the years a student could plausibly be reviewing. */
export function academicYearOptions(count = 6) {
  const current = currentAcademicYear();
  return Array.from({ length: count }, (_, i) => current - i);
}

/** (2025, 1) -> "AY25/26 Sem 1"; null for reviews written before the term was asked. */
export function formatTerm(academicYear, semester) {
  if (!academicYear || !semester) return null;
  const sem = SEMESTERS.find((s) => s.value === semester);
  return `${formatAcademicYear(academicYear)} ${sem ? sem.short : `Sem ${semester}`}`;
}
