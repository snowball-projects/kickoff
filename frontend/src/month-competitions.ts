import { leagueVisual } from "./calendar-helpers";
import { eventInstant, eventTimeBucket } from "./date-utils";
import type { EventCard } from "./types";

// Reviewed sessions carry their meet/stop before the category. A tournament
// has its own title; league identities join season fixtures (NFL, etc.).
export function monthCompetition(event: EventCard) {
  const meet = event.event_type === "session" && ["climbing", "weightlifting"].includes(event.sport)
    ? event.title.split(event.sport === "climbing" ? " — " : " · ")[0]
    : event.event_type === "tournament" ? event.title : "";
  return {
    key: JSON.stringify([event.sport, event.league, event.season, meet]),
    name: meet || leagueVisual(event.league).shortLabel,
  };
}

export function monthCompetitions(items: EventCard[], counts: Record<string, number> = {}) {
  const groups = new Map<string, { key: string; name: string; items: EventCard[]; hidden: number }>();
  for (const event of items) {
    const { key, name } = monthCompetition(event);
    if (!groups.has(key)) groups.set(key, { key, name, items: [], hidden: 0 });
    groups.get(key)!.items.push(event);
  }
  return [...groups.values()].map((group) => ({ ...group,
    items: group.items.sort((a, b) => (eventInstant(a) ?? Infinity) - (eventInstant(b) ?? Infinity)
      || a.title.localeCompare(b.title) || a.event_id.localeCompare(b.event_id)),
    hidden: Math.max(0, (counts[group.key] || 0) - group.items.length),
  }));
}

export function competitionSummary(items: EventCard[], timezone: string) {
  const unit = items.every((event) => ["game", "match"].includes(event.event_type)) ? "games"
    : items.every((event) => event.event_type === "session") ? "sessions" : "events";
  const first = items.filter((event) => eventInstant(event) !== null)
    .sort((a, b) => eventInstant(a)! - eventInstant(b)!)[0];
  return `${items.length} ${unit} · ${first ? `from ${eventTimeBucket(first, timezone)}` : "Time TBD"}`;
}
