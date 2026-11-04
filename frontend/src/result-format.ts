export type ResultPerson = { name: string; participant_id?: string | null };
type ResultSource = {
  source_url: string; checked_date: string;
  allocation_source?: { source_url: string; checked_date: string; page?: number };
};
export type PodiumRow = ResultPerson & { rank: number };
export type PodiumResult = ResultSource & { kind: "podium"; rows: readonly PodiumRow[] };
export type GroupedPodiumResult = ResultSource & {
  kind: "podiums";
  categories: readonly { label: string; rows: readonly PodiumRow[] }[];
};
export type TennisSet = { value: number; tiebreak?: number; winner?: boolean };
export type TennisFinalResult = ResultSource & {
  kind: "tennis-final";
  winner: ResultPerson;
  runner_up: ResultPerson;
  status: "final" | "retired" | "walkover";
  score?: { winner: readonly TennisSet[]; runner_up: readonly TennisSet[] };
};
export type WeightliftingAttempt = { weight_kg: number | null; status: "made" | "missed" | "unused" };
export type WeightliftingAthlete = {
  lot?: string;
  name: string;
  nation: string;
  gender: string;
  weight_class: string;
  group: string | null;
  guest?: boolean;
  total_rank: number | null;
  snatch_rank?: number | null;
  clean_and_jerk_rank?: number | null;
  total_kg: number | null;
  snatch: readonly WeightliftingAttempt[];
  clean_and_jerk: readonly WeightliftingAttempt[];
  country_code?: string;
};
export type WeightliftingMedalist = {
  name: string; nation: string; rank: number; gender: string; weight_class: string;
  weight_kg?: number; country_code?: string; source_article_url?: string; lot?: string;
};
export type WeightliftingSource = ResultSource & { gender: string; weight_class: string; revision?: string };
export type WeightliftingResult = ResultSource & {
  kind: "weightlifting";
  athletes: readonly WeightliftingAthlete[];
  total_medalists: readonly WeightliftingMedalist[];
  snatch_medalists: readonly WeightliftingMedalist[];
  clean_and_jerk_medalists: readonly WeightliftingMedalist[];
  sources?: readonly WeightliftingSource[];
  medal_classes: readonly { gender: string; weight_class: string }[];
  mixed_classes: boolean;
};
export type EventResult = PodiumResult | GroupedPodiumResult | TennisFinalResult | WeightliftingResult;

export function resultRows(result: PodiumResult | TennisFinalResult): (ResultPerson & { label: string })[] {
  if (result.kind === "podium") return result.rows.map(row => ({
    name: row.name, participant_id: row.participant_id, label: String(row.rank),
  }));
  return [
    { name: result.winner.name, participant_id: result.winner.participant_id, label: "Champion" },
    { name: result.runner_up.name, participant_id: result.runner_up.participant_id, label: "Runner-up" },
  ];
}

export function tennisSets(result: TennisFinalResult) {
  // The producer supplies paired arrays. Keep the match winner's orientation
  // even when that player lost a set; no set outcome is inferred from values.
  const score = result.score;
  return score ? score.winner.map((winner, index) => ({ winner, runner_up: score.runner_up[index] })) : [];
}

export function tennisSetLabel(set: TennisSet) {
  return `${set.value}${set.tiebreak === undefined ? "" : ` (tie-break ${set.tiebreak})`}${set.winner === true ? ", set winner" : ""}`;
}

export function tennisStatusLabel(status: TennisFinalResult["status"]) {
  return { final: "Final", retired: "Retired", walkover: "Walkover" }[status];
}

export function weightliftingMedalists(result: WeightliftingResult, rows = result.total_medalists) {
  return rows.filter(athlete => result.medal_classes.some(category =>
    category.gender === athlete.gender && category.weight_class === athlete.weight_class));
}

export function weightliftingClass(athlete: { gender: string; weight_class: string; group?: string | null }) {
  const gender = athlete.gender === "women" ? "Women's" : athlete.gender === "men" ? "Men's" : athlete.gender;
  return `${gender} ${athlete.weight_class} kg${athlete.group ? ` · Group ${athlete.group}` : ""}`;
}

export function weightliftingTotal(athlete: WeightliftingAthlete) {
  return athlete.total_kg === null ? "" : `${athlete.total_kg} kg`;
}

export function attemptLabel(attempt: WeightliftingAttempt) {
  if (attempt.status === "unused") return "Unused";
  return `${attempt.weight_kg === null ? "" : `${attempt.weight_kg} kg, `}${attempt.status}`;
}

export function resultSummary(result?: EventResult | null): string {
  if (!result) return "";
  if (result.kind === "podium") return resultRows(result).map(row => `${row.label} ${row.name}`).join(" · ");
  if (result.kind === "podiums") return result.categories.map(category =>
    `${category.label}: ${resultSummary({ ...result, kind: "podium", rows: category.rows })}`).join(" · ");
  if (result.kind === "weightlifting") return weightliftingMedalists(result).map(athlete =>
    `${weightliftingClass(athlete)}: ${athlete.rank} ${athlete.name}`).join(" · ");
  const value = (set: TennisSet) => `${set.value}${set.tiebreak === undefined ? "" : `(${set.tiebreak})`}`;
  const score = tennisSets(result).map(set => `${value(set.winner)}–${value(set.runner_up)}`).join(", ");
  return [`Champion ${result.winner.name}`, `Runner-up ${result.runner_up.name}`, score, tennisStatusLabel(result.status)].filter(Boolean).join(" · ");
}
