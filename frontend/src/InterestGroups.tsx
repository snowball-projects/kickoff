import { useEffect, useRef } from "react";
import { interestGroups, leagueVisual, SOCCER_COUNTRIES, toggleInterestGroup } from "./calendar-helpers";

function GroupCheckbox({ name, selected, total, onChange }: {
  name: string; selected: number; total: number; onChange: () => void;
}) {
  const input = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (input.current) input.current.indeterminate = selected > 0 && selected < total;
  }, [selected, total]);
  return (
    <label className="group-selection">
      <input ref={input} type="checkbox" checked={selected === total} onChange={onChange}
        aria-label={`Select all ${name}`} />
      <span aria-hidden="true">{selected}/{total}</span>
    </label>
  );
}

export default function InterestGroups({ leagues, selected, onChange }: {
  leagues: { value: string }[]; selected: string[]; onChange: (value: string[]) => void;
}) {
  return (
    <div className="interest-groups">
      {interestGroups(leagues).map((group) => (
        <section className="interest-group" key={group.name} aria-label={`${group.name} interests`}>
          <GroupCheckbox name={group.name} total={group.leagues.length}
            selected={group.leagues.filter((league) => selected.includes(league)).length}
            onChange={() => onChange(toggleInterestGroup(selected, group.leagues))} />
          <details>
            <summary>{group.name}</summary>
            <div className="interest-grid">
              {group.leagues.map((league) => {
                const country = SOCCER_COUNTRIES[league];
                return (
                  <label key={league} className={`interest ${selected.includes(league) ? "chosen" : ""}`}>
                    <input type="checkbox" checked={selected.includes(league)}
                      onChange={() => onChange(selected.includes(league)
                        ? selected.filter((value) => value !== league) : [...selected, league])} />
                    {country ? <span className="country-flag" role="img" aria-label={country.name}>{country.flag}</span>
                      : <span aria-hidden="true" className={`interest-dot ${leagueVisual(league).className}`} />}
                    <span>{leagueVisual(league).shortLabel}</span>
                  </label>
                );
              })}
            </div>
          </details>
        </section>
      ))}
    </div>
  );
}
