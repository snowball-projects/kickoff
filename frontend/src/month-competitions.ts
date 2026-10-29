import { leagueVisual } from "./calendar-helpers";
import type { EventCard } from "./types";

// Reviewed sessions carry their meet/stop before the category. A tournament
// has its own title; league identities join season fixtures (NFL, etc.).
export function monthCompetition(event: EventCard) {
  const climbingParts = event.title.split(" · ");
  const meet = event.event_type === "session" && ["climbing", "weightlifting"].includes(event.sport)
    ? event.sport === "climbing"
      ? climbingParts.slice(0, -1).join(" · ") || event.title
      : event.title.split(" · ")[0]
    : event.event_type === "tournament" ? event.title : "";
  return {
    key: JSON.stringify([event.sport, event.league, event.season, meet]),
    name: meet || leagueVisual(event.league).shortLabel,
  };
}
