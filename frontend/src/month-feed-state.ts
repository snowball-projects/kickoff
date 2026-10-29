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
