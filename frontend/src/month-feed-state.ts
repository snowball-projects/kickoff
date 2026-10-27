export const MONTH_WINDOW_SIZE = 9;

export function monthIndex(anchor: string) {
  return Number(anchor.slice(0, 4)) * 12 + Number(anchor.slice(5, 7)) - 1;
}
export function monthAt(index: number) {
  return `${Math.floor(index / 12)}-${String(index % 12 + 1).padStart(2, "0")}-01`;
}
export function scheduleWindow(today: string) {
  return { start: dayInMonth(today, -12), end: dayInMonth(today, 12) };
}
export function boundMonth(anchor: string, today: string) {
  const { start, end } = scheduleWindow(today);
  return monthAt(Math.max(monthIndex(start), Math.min(monthIndex(end), monthIndex(anchor))));
}
export function monthWindow(center: string, today: string) {
  const bounds = scheduleWindow(today);
  const start = Math.max(monthIndex(bounds.start), Math.min(
    monthIndex(bounds.end) - MONTH_WINDOW_SIZE + 1,
    monthIndex(center) - Math.floor(MONTH_WINDOW_SIZE / 2),
  ));
  return Array.from({ length: MONTH_WINDOW_SIZE }, (_, i) => monthAt(start + i));
}
export function shouldRecenter(anchors: string[], visible: string, today: string) {
  const { start, end } = scheduleWindow(today);
  const index = anchors.indexOf(visible);
  return (index < 2 && monthIndex(anchors[0]) !== monthIndex(start)) ||
    (index >= anchors.length - 2 && monthIndex(anchors.at(-1)!) !== monthIndex(end));
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
