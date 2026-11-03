import type { ApiParticipant } from "./types";

export function startList(participants: ApiParticipant[]) {
  return participants.filter(participant => participant.entity_type === "athlete" && participant.entry_total_kg !== undefined)
    .sort((a, b) => b.entry_total_kg! - a.entry_total_kg! || a.name.localeCompare(b.name, "en"));
}
