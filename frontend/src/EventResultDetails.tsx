import { countryIdentity } from "./countries";
import { attemptLabel, resultRows, tennisSetLabel, tennisSets, tennisStatusLabel, weightliftingClass, weightliftingMedalists, weightliftingTotal } from "./result-format";
import type { EventResult, PodiumRow, TennisFinalResult, WeightliftingAthlete, WeightliftingAttempt, WeightliftingMedalist, WeightliftingResult } from "./result-format";
import "./results.css";

export type { EventResult } from "./result-format";

function PodiumTable({ rows, label = "Podium" }: { rows: readonly PodiumRow[]; label?: string }) {
  return <div className="event-result-table-wrap"><table aria-label={label} className="event-result-podium">
    <thead><tr><th scope="col">Rank</th><th scope="col">Competitor</th></tr></thead>
    <tbody>{rows.map((row, index) => <tr key={`${row.rank}-${index}`}>
      <td>{row.rank}</td><th scope="row">{row.name}</th>
    </tr>)}</tbody>
  </table></div>;
}

function TennisResult({ result }: { result: TennisFinalResult }) {
  const sets = tennisSets(result);
  return <>
    <p className="event-result-status">{tennisStatusLabel(result.status)}</p>
    <div className="event-result-table-wrap"><table aria-label="Singles final" className="event-result-tennis">
      <thead><tr><th scope="col">Player</th>{sets.map((_, index) => <th key={index} scope="col">Set {index + 1}</th>)}</tr></thead>
      <tbody>{resultRows(result).map((row, player) => <tr key={player}>
        <th scope="row"><small>{row.label}</small>{row.name}</th>
        {sets.map((set, index) => {
          const score = player === 0 ? set.winner : set.runner_up;
          return <td key={index} aria-label={tennisSetLabel(score)} className={score.winner === true ? "event-result-set-winner" : undefined}>
            <span aria-hidden="true">{score.value}{score.tiebreak !== undefined && <sup>{score.tiebreak}</sup>}</span>
          </td>;
        })}
      </tr>)}</tbody>
    </table></div>
  </>;
}

function AthleteName({ athlete, medalist = false, mixed = false }: { athlete: WeightliftingAthlete | WeightliftingMedalist; medalist?: boolean; mixed?: boolean }) {
  const country = countryIdentity(athlete.country_code);
  return <>
    <span className="event-result-athlete-name">{country?.flag && <span role="img" aria-label={country.name}>{country.flag} </span>}{athlete.name}</span>
    {!medalist && <small>{athlete.nation}{"guest" in athlete && athlete.guest && " · Guest"}</small>}
    {(!medalist || mixed) && <small>{weightliftingClass(athlete)}</small>}
  </>;
}

function AttemptCell({ attempt, lift, number }: { attempt: WeightliftingAttempt; lift: string; number: number }) {
  return <td className="event-result-attempt" aria-label={`${lift} attempt ${number}, ${attemptLabel(attempt)}`}>
    {attempt.status === "unused" ? "Unused" : <>
      {attempt.status === "missed" ? <s aria-hidden="true">{attempt.weight_kg}</s> : <span aria-hidden="true">{attempt.weight_kg}</span>}
      <small aria-hidden="true"><span>{attempt.status === "made" ? "✓" : "×"}</span> {attempt.status === "made" ? "Made" : "Missed"}</small>
    </>}
  </td>;
}

function WeightliftingResults({ result }: { result: WeightliftingResult }) {
  const medals = [
    { label: "Total medalists", rows: weightliftingMedalists(result) },
    { label: "Snatch medalists", rows: weightliftingMedalists(result, result.snatch_medalists) },
    { label: "Clean & jerk medalists", rows: weightliftingMedalists(result, result.clean_and_jerk_medalists) },
  ];
  return <>
    {medals.filter(medal => medal.rows.length > 0).map(({ label, rows }) => <section aria-label={label} className="event-result-medalists" key={label}>
      <h5>{label}</h5>
      <ol>{rows.map((athlete, index) => <li key={index}>
        <AthleteName athlete={athlete} medalist mixed={result.mixed_classes} />
        <small>Rank {athlete.rank}{athlete.weight_kg != null && ` · ${athlete.weight_kg} kg`}</small>
      </li>)}</ol>
    </section>)}
    {result.athletes.length > 0 && <>
    <h5>Attempts</h5>
    <div className="event-result-lifts-wrap" role="region" aria-label="Athlete attempts" tabIndex={0}>
      <table className="event-result-lifts" aria-label="Weightlifting attempts and totals">
        <thead>
          <tr><th scope="col" rowSpan={2}>Athlete</th><th scope="colgroup" colSpan={3}>Snatch (kg)</th>
            <th scope="colgroup" colSpan={3}>Clean &amp; jerk (kg)</th><th scope="col" rowSpan={2}>Total</th><th scope="col" rowSpan={2}>Rank</th></tr>
          <tr>{["Snatch", "Clean & jerk"].flatMap(lift => [1, 2, 3].map(number => <th scope="col" key={`${lift}-${number}`} aria-label={`${lift} attempt ${number}`}>{number}</th>))}</tr>
        </thead>
        <tbody>{result.athletes.map((athlete, index) => <tr key={index}>
          <th scope="row"><AthleteName athlete={athlete} /></th>
          {athlete.snatch.map((attempt, i) => <AttemptCell key={`snatch-${i}`} attempt={attempt} lift="Snatch" number={i + 1} />)}
          {athlete.clean_and_jerk.map((attempt, i) => <AttemptCell key={`clean-${i}`} attempt={attempt} lift="Clean & jerk" number={i + 1} />)}
          <td className="event-result-total">{weightliftingTotal(athlete)}</td><td className="event-result-rank">{athlete.total_rank}</td>
        </tr>)}</tbody>
      </table>
    </div>
    </>}
  </>;
}

export default function EventResultDetails({ result }: { result?: EventResult | null }) {
  if (!result) return null;
  return <section className="event-result-details" aria-label="Result">
    <h4>Result</h4>
    {result.kind === "podium" && <PodiumTable rows={result.rows} />}
    {result.kind === "podiums" && result.categories.map((category, index) => <section className="event-result-category" key={index}>
      <h5>{category.label}</h5><PodiumTable rows={category.rows} label={`${category.label} podium`} />
    </section>)}
    {result.kind === "tennis-final" && <TennisResult result={result} />}
    {result.kind === "weightlifting" && <WeightliftingResults result={result} />}
    {result.kind === "weightlifting" && result.sources?.length ? result.sources.map((source, index) => <p className="event-result-source" key={index}>
      <a href={source.source_url} target="_blank" rel="noreferrer">{weightliftingClass(source)} result source ↗</a>
      {" · "}Checked {source.checked_date}{source.revision && ` · ${source.revision}`}
    </p>) : <p className="event-result-source"><a href={result.source_url} target="_blank" rel="noreferrer">Result source ↗</a>
      {" · "}Checked {result.checked_date}</p>}
    {result.allocation_source && <p className="event-result-source">
      <a href={result.allocation_source.source_url} target="_blank" rel="noreferrer">Session source ↗</a>
      {" · "}Checked {result.allocation_source.checked_date}{result.allocation_source.page != null && ` · Page ${result.allocation_source.page}`}
    </p>}
  </section>;
}
