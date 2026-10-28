import { useEffect, useRef } from "react";
import { SportIcon } from "./EventIdentity";
import { CLIMBING_DISCIPLINES, GENDERS, GOLF_TOURS, type InterestPreferences } from "./interest-preferences";
import { interestChoices, interestGroups, leagueVisual, SOCCER_COUNTRIES, toggleInterestGroup } from "./calendar-helpers";

function SelectionCheckbox({ name, selected, total, onChange }: {
  name?: string; selected: number; total: number; onChange: () => void;
}) {
  const input = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (input.current) input.current.indeterminate = selected > 0 && selected < total;
  }, [selected, total]);
  return <input ref={input} type="checkbox" checked={selected === total} onChange={onChange} aria-label={name} />;
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

function PreferenceCheckbox({ name, checked, onChange }: {
  name: string; checked: boolean; onChange: (checked: boolean) => void;
}) {
  return <label className={`interest ${checked ? "chosen" : ""}`}>
    <input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} />
    <span>{name}</span>
  </label>;
}

export default function InterestGroups({ leagues, selected, onChange, preferences, onPreferencesChange }: {
  leagues: { value: string }[]; selected: string[]; onChange: (value: string[]) => void;
  preferences: InterestPreferences; onPreferencesChange: (value: InterestPreferences) => void;
}) {
  return (
    <div className="interest-groups">
      {interestGroups(leagues).map((group) => {
        const sport = group.name === "Climbing" ? "climbing" : group.name === "Weightlifting" ? "weightlifting" : null;
        const count = group.leagues.filter((league) => selected.includes(league)).length;
        return (
          <section className="interest-group" key={group.name} aria-label={`${group.name} interests`}>
            <label className="group-selection">
              <SelectionCheckbox name={`Select all ${group.name}`} total={group.leagues.length} selected={count}
                onChange={() => onChange(toggleInterestGroup(selected, group.leagues))} />
              <span aria-hidden="true">{count}/{group.leagues.length}</span>
            </label>
            <details>
              <summary><SportIcon sport={group.name} />{group.name}</summary>
              <div className="interest-grid">
                {interestChoices(group).map((choice) => {
                  const league = choice.leagues[0];
                  const country = SOCCER_COUNTRIES[league];
                  const count = choice.leagues.filter((league) => selected.includes(league)).length;
                  return (
                    <label key={league} className={`interest ${count ? "chosen" : ""}`}>
                      <SelectionCheckbox total={choice.leagues.length} selected={count}
                        onChange={() => onChange(toggleInterestGroup(selected, choice.leagues))} />
                      {country ? <span className="country-flag" role="img" aria-label={country.name}>{country.flag}</span>
                        : <span aria-hidden="true" className={`interest-dot ${leagueVisual(league).className}`} />}
                      <span>{choice.name}</span>
                    </label>
                  );
                })}
              </div>
              {group.name === "Golf" && <fieldset className="interest-facet">
                <legend>Events</legend>
                <div className="interest-grid">
                  {GOLF_TOURS.filter((tour) => group.leagues.includes(tour)).map((tour) => (
                    <PreferenceCheckbox key={tour} name={`${leagueVisual(tour).shortLabel} majors only`}
                      checked={preferences.golf_views[tour] === "majors_only"} onChange={(checked) =>
                        onPreferencesChange({ ...preferences, golf_views: { ...preferences.golf_views,
                          [tour]: checked ? "majors_only" : "full_tour" } })} />
                  ))}
                </div>
              </fieldset>}
              {group.name === "Motorsports" && <fieldset className="interest-facet">
                <legend>Events</legend>
                <div className="interest-grid">
                  <PreferenceCheckbox name="Races only" checked={preferences.motorsport_view === "race_only"}
                    onChange={(checked) => onPreferencesChange({ ...preferences,
                      motorsport_view: checked ? "race_only" : "full_weekend" })} />
                </div>
              </fieldset>}
              {sport && <FacetChoices name="Gender" values={GENDERS} selected={preferences[sport].genders}
                onChange={(genders) => onPreferencesChange({ ...preferences,
                  [sport]: { ...preferences[sport], genders } })} />}
              {sport === "climbing" && <FacetChoices name="Discipline" values={CLIMBING_DISCIPLINES}
                selected={preferences.climbing.disciplines} onChange={(disciplines) =>
                  onPreferencesChange({ ...preferences, climbing: { ...preferences.climbing, disciplines } })} />}
            </details>
          </section>
        );
      })}
    </div>
  );
}
