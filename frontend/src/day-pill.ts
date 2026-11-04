import { agendaEventText } from "./agenda-title";
import { participantRoles } from "./participants";
import type { EventCard } from "./types";

export function dayPillTeams(event: EventCard) {
  const { home, away } = participantRoles(event);
  if (!home || !away) return null;
  if (["football", "american-football", "basketball", "baseball", "hockey"].includes(event.sport))
    return { teams: [away, home], separator: "at" };
  if (["soccer", "rugby", "cricket"].includes(event.sport))
    return { teams: [home, away], separator: "vs" };
  return null;
}

export function dayPillTitle(event: EventCard) {
  // Without both source roles, the source title retains its order and any
  // undecided opponent. It must not become an invented home/away matchup.
  if (["football", "american-football", "basketball", "baseball", "hockey", "soccer", "rugby", "cricket"].includes(event.sport))
    return event.title;
  const { title, session } = agendaEventText(event);
  const round = event.week_label || event.round_or_stage;
  return event.sport === "golf" && round && !title.toLowerCase().includes(round.toLowerCase()) ? `${title}, ${round}`
    : [title, session].filter(Boolean).join(" · ");
}
