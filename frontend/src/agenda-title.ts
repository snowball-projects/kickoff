import { leagueTitleNames } from "./calendar-helpers";
import type { EventCard } from "./types";

const words = (text: string) => [...text.matchAll(/[\p{L}\p{N}]+/gu)];
// These describe the event's level, even inside a competition's name.
const level = /^(?:youth|junior|senior|para|u\d+)$/i;

export function agendaEventTitle(event: Pick<EventCard, "title" | "league" | "sport" | "city" | "venue">) {
  const titleWords = words(event.title);
  const names = leagueTitleNames(event.league, event.sport)
    .map(words).sort((a, b) => b.length - a.length);
  for (const name of names) {
    let next = 0;
    const retained: string[] = [];
    for (const word of name) {
      while (next > 0 && titleWords[next]?.[0].toLowerCase() !== word[0].toLowerCase()
        && level.test(titleWords[next]?.[0] || "")) retained.push(titleWords[next++][0]);
      if (titleWords[next]?.[0].toLowerCase() !== word[0].toLowerCase()) break;
      next++;
    }
    // Match complete identities at the start, never substrings or later words.
    if (!name.length || next - retained.length !== name.length) continue;
    const last = titleWords[next - 1];
    const suffix = event.title.slice(last.index! + last[0].length)
      .replace(/^[\s·:./|–-]+/u, "").replace(/^at\s+/i, "");
    const specific = [...retained, suffix].filter(Boolean).join(" · ");
    // Some date-only announcements name only the competition. Use a published
    // location when available; never invent a session or an event number.
    return specific || event.city || event.venue || "";
  }
  return event.title;
}
