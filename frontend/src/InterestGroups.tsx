import { useEffect, useRef } from "react";
import { CLIMBING_DISCIPLINES, GENDERS, type SessionInterests } from "./interest-preferences";
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

function FacetChoices({ name, values, selected, onChange }: {
  name: string; values: readonly string[]; selected: string[]; onChange: (value: string[]) => void;
}) {
  return (
    <fieldset className="interest-facet">
      <legend>{name}</legend>
      <div className="interest-grid">
        {values.map((value) => (
          <label className={`interest ${selected.includes(value) ? "chosen" : ""}`} key={value}>
            <input type="checkbox" checked={selected.includes(value)} onChange={() =>
              onChange(selected.includes(value) ? selected.filter((item) => item !== value) : [...selected, value])} />
            <span>{value}</span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}

export default function InterestGroups({ leagues, selected, onChange, sessionInterests, onSessionChange }: {
  leagues: { value: string }[]; selected: string[]; onChange: (value: string[]) => void;
  sessionInterests: SessionInterests; onSessionChange: (value: SessionInterests) => void;
}) {
  return (
    <div className="interest-groups">
      {interestGroups(leagues).map((group) => {
        const sport = group.name === "Climbing" ? "climbing" : group.name === "Weightlifting" ? "weightlifting" : null;
        return (
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
                      <span>{league === "IFSC_WORLD_CUP" ? "World Cups" : leagueVisual(league).shortLabel}</span>
                    </label>
                  );
                })}
              </div>
              {sport && <FacetChoices name="Gender" values={GENDERS} selected={sessionInterests[sport].genders}
                onChange={(genders) => onSessionChange({ ...sessionInterests,
                  [sport]: { ...sessionInterests[sport], genders } })} />}
              {sport === "climbing" && <FacetChoices name="Discipline" values={CLIMBING_DISCIPLINES}
                selected={sessionInterests.climbing.disciplines} onChange={(disciplines) =>
                  onSessionChange({ ...sessionInterests, climbing: { ...sessionInterests.climbing, disciplines } })} />}
            </details>
          </section>
        );
      })}
    </div>
  );
}
