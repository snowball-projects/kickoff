import { countryIdentity } from "./countries";
import type { ApiParticipant } from "./types";
import { startList } from "./weightlifting-startlist";
import "./WeightliftingStartList.css";

export default function WeightliftingStartList({ participants }: { participants: ApiParticipant[] }) {
  const entries = startList(participants);
  if (!entries.length) return null;
  const source = entries[0];
  const combined = new Set(entries.map(entry => entry.start_list_category)).size > 1;
  return <section className="weightlifting-start-list" aria-label="Start list">
    <h4>Start list</h4>
    <ol>{entries.slice(0, 10).map(entry => {
      const country = countryIdentity(entry.country_code);
      return <li key={entry.participant_id || entry.name}>
        <span>{country?.flag && <span role="img" aria-label={country.name}>{country.flag}</span>} {entry.name}
          {entry.start_list_nation && <small> {entry.start_list_nation}</small>}
          {entry.start_list_guest && <small> · Guest</small>}
          {combined && <small className="start-list-category">{entry.start_list_category}</small>}
        </span>
        <span className="start-list-total">{entry.entry_total_kg} kg</span>
      </li>;
    })}</ol>
    {entries.length > 10 && <p>and {entries.length - 10} more</p>}
    <p className="start-list-source"><a href={source.start_list_source_url} target="_blank" rel="noreferrer">Start list source ↗</a>
      {source.start_list_checked_date && <> · Checked {source.start_list_checked_date}</>}
    </p>
  </section>;
}
