import { eventInstant } from "./date-utils";
import type { EventCard } from "./types";

function easternDate(instant: number) {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "America/New_York", year: "numeric", month: "2-digit", day: "2-digit" }).format(instant);
}

const PROMOTIONS: Record<string, string> = { UFC: "ufc", PFL: "pfl", ONE: "ofc", RIZIN: "rizin" };
export function fightCardRequest(event: EventCard) {
  const promotion = PROMOTIONS[event.league];
  if (!promotion) return null;
  // ESPN's date filter uses Eastern calendar dates, including overnight cards.
  const instant = eventInstant(event);
  const date = instant !== null
    ? easternDate(instant)
    : event.calendar_date;
  if (!date) return null;
  const id = event.source === "espn" ? /^espn-[a-z_]+-(\d+)$/.exec(event.event_id)?.[1] : undefined;
  return { promotion, date, id, title: event.title,
    // The web host serves the same scoreboard with browser CORS, like golf.
    url: `https://site.web.api.espn.com/apis/site/v2/sports/mma/${promotion}/scoreboard?dates=${date.replaceAll("-", "")}` };
}

type Fighter = { id?: string; order?: number; athlete?: { displayName?: string };
  records?: { type?: string; summary?: string }[]; winner?: boolean };
type Bout = { id?: string; date?: string; type?: { abbreviation?: string };
  status?: { period?: number; displayClock?: string; type?: { completed?: boolean; shortDetail?: string } }; competitors?: Fighter[] };
type Payload = { events?: { id?: string; name?: string; date?: string; competitions?: Bout[] }[] };
export type FightCardData = { sourceUrl: string; blocks: { start: string; label: string; bouts: {
  id: string; weight: string; result: string; fighters: { id: string; name: string; record: string; winner: boolean }[];
}[] }[] };
const titleKey = (title: string) => title.normalize("NFKC").trim().replace(/\s+/g, " ").toLowerCase();

export function readFightCard(payload: Payload, request: NonNullable<ReturnType<typeof fightCardRequest>>): FightCardData | null {
  const matches = payload?.events?.filter((item) => {
    const instant = item.date && /(?:Z|[+-]\d{2}:?\d{2})$/i.test(item.date) ? Date.parse(item.date) : NaN;
    return Number.isFinite(instant) && easternDate(instant) === request.date && (request.id ? item.id === request.id
      : item.name && titleKey(item.name) === titleKey(request.title));
  });
  // Never substitute the first event on a shared date, or choose an ambiguous title.
  if (matches?.length !== 1 || !matches[0].id) return null;
  const event = matches[0];
  const groups = new Map<number, FightCardData["blocks"][number]>();
  // Scoreboards list bouts from the opener to the main event, as ESPN fightcenter confirms.
  for (const bout of [...(event.competitions || [])].reverse()) {
    const start = bout.date && /(?:Z|[+-]\d{2}:?\d{2})$/i.test(bout.date) ? Date.parse(bout.date) : NaN;
    if (!bout.id || !Number.isFinite(start) || bout.competitors?.length !== 2
      || bout.competitors.some((fighter) => !fighter.athlete?.displayName)) continue;
    const completed = bout.status?.type?.completed === true;
    const result = completed ? [bout.status?.type?.shortDetail, bout.status?.period && `R${bout.status.period}`, bout.status?.displayClock].filter(Boolean).join(" · ") : "";
    const fighters = [...bout.competitors].sort((a, b) => (a.order || 0) - (b.order || 0)).map((fighter) => ({
      id: fighter.id || fighter.athlete!.displayName!, name: fighter.athlete!.displayName!,
      record: fighter.records?.find((record) => record.type === "total")?.summary || "",
      winner: completed && fighter.winner === true,
    }));
    if (!groups.has(start)) groups.set(start, { start: bout.date!, label: "", bouts: [] });
    groups.get(start)!.bouts.push({ id: bout.id, weight: bout.type?.abbreviation || "", result, fighters });
  }
  const blocks = [...groups.entries()].sort(([a], [b]) => b - a).map(([, block], index) => ({ ...block,
    label: ["Main card", "Prelims", "Early prelims"][index] || "" }));
  return blocks.length ? { sourceUrl: `https://www.espn.com/mma/fightcenter/_/id/${event.id}/league/${request.promotion}`, blocks } : null;
}
