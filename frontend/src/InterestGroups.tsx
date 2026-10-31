import { useLayoutEffect, useRef, useState } from "react";
import { SportIcon } from "./EventIdentity";
import { allPreferences, CLIMBING_DISCIPLINES, GENDERS, MOTORSPORT_EVENTS, type InterestPreferences, type LeagueInterest } from "./interest-preferences";
import { CATEGORY_KEYS, interestChoices, interestGroups, leagueVisual, SOCCER_COUNTRIES, toggleInterestGroup } from "./calendar-helpers";

function OptionPills({ name, values, selected, onChange }: {
  name: string; values: readonly string[]; selected: string[]; onChange: (value: string[]) => void;
}) {
  return <fieldset className="interest-facet">
    <legend>{name}</legend>
    <div className="interest-pills">{values.map((value) => <button type="button" className="interest-pill" key={value}
      aria-pressed={selected.includes(value)} onClick={() => onChange(selected.includes(value)
        ? selected.filter((item) => item !== value) : [...selected, value])}>
      {value[0].toUpperCase() + value.slice(1)}
    </button>)}</div>
  </fieldset>;
}

export default function InterestGroups({ leagues, preferences, onChange }: {
  leagues: LeagueInterest[]; preferences: InterestPreferences; onChange: (value: InterestPreferences) => void;
}) {
  const [open, setOpen] = useState<string | null>(null);
  const [trayAfter, setTrayAfter] = useState(0);
  const panel = useRef<HTMLDivElement>(null);
  const available = interestGroups(leagues);
  const groups = Object.keys(CATEGORY_KEYS).map((name) => ({ name,
    leagues: available.find((group) => group.name === name)?.leagues || [] }));
  const selected = preferences.leagues;
  const leagueSports = new Map(leagues.map(({ value, sport }) => [value, sport]));
  const active = groups.find((group) => group.name === open);
  useLayoutEffect(() => {
    if (!open) return;
    const element = panel.current!;
    const measure = () => {
      const buttons = [...element.querySelectorAll<HTMLButtonElement>(".sport-pill")];
      const gap = parseFloat(getComputedStyle(element).columnGap);
      const index = groups.findIndex((group) => group.name === open);
      let used = 0, first = 0;
      // Measure the natural wrapped rows independently of the full-width tray.
      for (const [i, button] of buttons.entries()) {
        const width = button.getBoundingClientRect().width;
        if (used && used + gap + width > element.clientWidth + .5) {
          if (index >= first && index < i) { setTrayAfter(i - 1); return; }
          first = i; used = 0;
        }
        used += (used ? gap : 0) + width;
      }
      setTrayAfter(buttons.length - 1);
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    return () => observer.disconnect();
  }, [open, selected, leagues]);
  function changeLeagues(group: typeof groups[number], next: string[]) {
    const value = { ...preferences, leagues: next };
    if (!group.leagues.some((league) => selected.includes(league))) {
      const all = allPreferences(next);
      if (group.name === "Motorsports") value.motorsport_events = all.motorsport_events;
      if (group.name === "Climbing") value.climbing = all.climbing;
      if (group.name === "Weightlifting") value.weightlifting = all.weightlifting;
    }
    onChange(value);
  }
  return <div className="sport-pills" ref={panel}>
    {groups.flatMap((group, index) => {
      const count = group.leagues.filter((league) => selected.includes(league)).length;
      const partial = count > 0 && count < group.leagues.length;
      const single = ["Football", "Basketball", "Baseball", "Hockey"].includes(group.name);
      const category = CATEGORY_KEYS[group.name as keyof typeof CATEGORY_KEYS];
      return [<button key={group.name} type="button" className={`sport-pill category-${category}${partial ? " partial" : ""}`}
          aria-label={group.name} aria-pressed={partial ? "mixed" : count > 0}
          aria-describedby={partial ? `count-${category}` : undefined}
          aria-expanded={single ? undefined : open === group.name}
          aria-controls={single ? undefined : `tray-${category}`} disabled={!group.leagues.length}
          onClick={() => {
            if (single) { changeLeagues(group, toggleInterestGroup(selected, group.leagues)); setOpen(null); }
            else if (!count) { changeLeagues(group, toggleInterestGroup(selected, group.leagues)); setOpen(group.name); }
            else setOpen(open === group.name ? null : group.name);
          }}>
          <SportIcon category={category} />{group.name}
          {partial && <span id={`count-${category}`}>{count}/{group.leagues.length}</span>}
        </button>,
        active && index === trayAfter && <section key="tray" className={`interest-tray category-${CATEGORY_KEYS[active.name as keyof typeof CATEGORY_KEYS]}`}
          id={`tray-${CATEGORY_KEYS[active.name as keyof typeof CATEGORY_KEYS]}`} aria-label={`${active.name} interests`}>
          <div className="interest-pills">
            <button type="button" className="interest-pill" aria-pressed={active.leagues.every((league) => selected.includes(league))}
              onClick={() => changeLeagues(active, toggleInterestGroup(selected, active.leagues))}>All</button>
            {interestChoices(active).map((choice) => {
              const league = choice.leagues[0], country = SOCCER_COUNTRIES[league];
              return <button type="button" key={league} className="interest-pill" aria-pressed={selected.includes(league)}
                onClick={() => changeLeagues(active, toggleInterestGroup(selected, choice.leagues))}>
                <span aria-hidden="true" className={`interest-swatch ${leagueVisual(league, leagueSports.get(league)).className}`} />
                {country && <span className="country-flag" role="img" aria-label={country.name}>{country.flag}</span>}{choice.name}
              </button>;
            })}
          </div>
          {active.name === "Motorsports" && <OptionPills name="Events" values={MOTORSPORT_EVENTS} selected={preferences.motorsport_events}
            onChange={(motorsport_events) => onChange({ ...preferences, motorsport_events })} />}
          {(active.name === "Climbing" || active.name === "Weightlifting") && <OptionPills name="Gender" values={GENDERS}
            selected={active.name === "Climbing" ? preferences.climbing.genders : preferences.weightlifting.genders}
            onChange={(genders) => onChange(active.name === "Climbing" ? { ...preferences, climbing: { ...preferences.climbing, genders } }
              : { ...preferences, weightlifting: { genders } })} />}
          {active.name === "Climbing" && <OptionPills name="Discipline" values={CLIMBING_DISCIPLINES} selected={preferences.climbing.disciplines}
            onChange={(disciplines) => onChange({ ...preferences, climbing: { ...preferences.climbing, disciplines } })} />}
        </section>];
    })}
  </div>;
}
