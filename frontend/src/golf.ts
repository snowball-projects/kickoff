import type { EventCard } from "./types";

export function isGolf(event: Pick<EventCard, "sport">) { return event.sport === "golf"; }

export function golfRound(event: EventCard, date: string, start: string): EventCard {
  const round = (Date.parse(`${date}T00:00:00Z`) - Date.parse(`${start}T00:00:00Z`)) / 86_400_000 + 1;
  return { ...event, title: `${event.title}, Round ${round}`, round_or_stage: `Round ${round}`,
    calendar_date: date, start_calendar_date: date, end_calendar_date: date,
    start_time_utc: null, start_time_local: null };
}

export function leaderboardId(event: Pick<EventCard, "source" | "event_id" | "sport">) {
  return isGolf(event) && event.source === "espn"
    ? /^espn-(?:pga_tour|lpga_tour)-(\d+)$/.exec(event.event_id)?.[1] : undefined;
}
export const LEADERBOARD_URL = "https://site.web.api.espn.com/apis/site/v2/sports/golf/leaderboard";

type Status = { type?: { state?: string; name?: string; completed?: boolean }; period?: number };
type Competitor = {
  id: string; sortOrder: number; athlete?: { displayName?: string }; score?: { displayValue?: string };
  status?: Status & { position?: { displayName?: string }; todayDetail?: string; detail?: string; teeTime?: string; thru?: number };
};
type Payload = { events?: { id?: string; status?: Status;
  competitions?: { status?: Status; competitors?: Competitor[] }[] }[] };
export type GolfLeaderboardData = {
  final: boolean; inProgress: boolean; round?: number; status: string | null;
  players: { id: string; name: string; position: string; total: string; today: string; thru: string }[];
};

// The endpoint supplies current standings or the final tournament result,
// never a historical snapshot of the selected calendar round.
export function readLeaderboard(payload: Payload, id: string, timezone: string, finalOnly: boolean): GolfLeaderboardData | null {
  const event = payload?.events?.[0];
  const competition = event?.competitions?.[0];
  const final = event?.status?.type?.completed === true || event?.status?.type?.name === "STATUS_FINAL";
  if (event?.id !== id || !competition || (finalOnly && !final) || !Array.isArray(competition.competitors)) return null;
  const players = competition.competitors
    .filter((player) => player?.athlete?.displayName && Number.isFinite(player.sortOrder))
    .sort((a, b) => a.sortOrder - b.sortOrder).slice(0, 5).map((player) => {
      const status = player.status;
      const tee = status?.teeTime && /(?:Z|[+-]\d{2}:?\d{2})$/i.test(status.teeTime) ? Date.parse(status.teeTime) : NaN;
      const today = status?.type?.state === "pre"
        ? Number.isFinite(tee) ? new Intl.DateTimeFormat(undefined, { hour: "numeric", minute: "2-digit", timeZone: timezone }).format(tee) : ""
        : /^(E|[+-]?\d+)(?:\(|$)/.exec(status?.todayDetail || status?.detail || "")?.[1] || "";
      return { id: player.id, name: player.athlete!.displayName!, position: status?.position?.displayName || "",
        total: player.score?.displayValue || "", today, thru: String(status?.thru ?? "") };
    });
  const state = competition.status?.type?.state;
  return players.length ? { final, inProgress: !final && state === "in",
    status: final ? "Final tournament" : state === "in" ? "In progress" : state === "pre" ? "Scheduled" : null,
    round: competition.status?.period, players } : null;
}
