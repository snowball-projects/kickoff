import type { EventCard } from "./types";

export function participantRoles(event: Pick<EventCard, "participants">) {
  return {
    home: event.participants.find((participant) => participant.role === "home") || null,
    away: event.participants.find((participant) => participant.role === "away") || null,
  };
}
