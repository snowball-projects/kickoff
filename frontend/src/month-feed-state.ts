// Calendar bounds keep ISO years four digits and date navigation well-defined.
export const FIRST_MONTH = "1900-01-01";
export const LAST_MONTH = "2100-12-01";
export const MONTH_WINDOW_SIZE = 9;

export function monthIndex(anchor: string) {
  return Number(anchor.slice(0, 4)) * 12 + Number(anchor.slice(5, 7)) - 1;
}
export function monthAt(index: number) {
  const bounded = Math.max(monthIndex(FIRST_MONTH), Math.min(monthIndex(LAST_MONTH), index));
  return `${Math.floor(bounded / 12)}-${String(bounded % 12 + 1).padStart(2, "0")}-01`;
}
export function monthWindow(center: string) {
  const start = Math.max(monthIndex(FIRST_MONTH), Math.min(
    monthIndex(LAST_MONTH) - MONTH_WINDOW_SIZE + 1,
    monthIndex(center) - Math.floor(MONTH_WINDOW_SIZE / 2),
  ));
  return Array.from({ length: MONTH_WINDOW_SIZE }, (_, i) => monthAt(start + i));
}
export function shouldRecenter(anchors: string[], visible: string) {
  const index = anchors.indexOf(visible);
  return (index < 2 && anchors[0] !== FIRST_MONTH) ||
    (index >= anchors.length - 2 && anchors.at(-1) !== LAST_MONTH);
}
export function visibleMonthAt(
  sections: { anchor: string; top: number }[],
  scrollTop: number,
  viewportHeight: number,
) {
  const probe = scrollTop + Math.min(180, viewportHeight * 0.3);
  return [...sections].reverse().find((section) => section.top <= probe)?.anchor ?? sections[0]?.anchor;
}
export function scrollBehavior(reducedMotion: boolean): ScrollBehavior {
  return reducedMotion ? "auto" : "smooth";
}
export function dayAfter(date: string, delta: number) {
  const value = new Date(`${date}T12:00:00Z`);
  value.setUTCDate(value.getUTCDate() + delta);
  return value.toISOString().slice(0, 10);
}
export function dayInMonth(date: string, delta: number) {
  const anchor = monthAt(monthIndex(date) + delta);
  const lastDay = new Date(Date.UTC(Number(anchor.slice(0, 4)), Number(anchor.slice(5, 7)), 0)).getUTCDate();
  return `${anchor.slice(0, 7)}-${String(Math.min(Number(date.slice(-2)), lastDay)).padStart(2, "0")}`;
}
