import { useLayoutEffect, useRef, useState, type ButtonHTMLAttributes } from "react";
import { leagueVisual, pillCountry } from "./calendar-helpers";
import { dayPillTeams, dayPillTitle } from "./day-pill";
import { SportIcon } from "./EventIdentity";
import TeamLogo from "./TeamLogo";
import type { EventCard } from "./types";

export default function DayPill({ event, compact = false, className = "", ...props }: {
  event: EventCard; compact?: boolean;
} & ButtonHTMLAttributes<HTMLButtonElement>) {
  const root = useRef<HTMLButtonElement>(null);
  const samples = useRef<HTMLSpanElement>(null);
  const [stage, setStage] = useState(0);
  const [failed, setFailed] = useState<ReadonlySet<string>>(() => new Set());
  const visual = leagueVisual(event.league, event.sport);
  const country = pillCountry([event]);
  const matchup = dayPillTeams(event);
  const title = dayPillTitle(event);
  const matchupName = matchup?.teams.map((team) => team.name).join(` ${matchup.separator} `);
  const sourceName = props["aria-label"] || event.title;
  const accessibleName = matchupName && !sourceName.includes(matchupName) ? `${sourceName}, ${matchupName}` : sourceName;
  const onFailure = (url: string) => setFailed((current) => current.has(url) ? current : new Set([...current, url]));

  useLayoutEffect(() => {
    const element = root.current!;
    const measurements = samples.current!;
    const phone = matchMedia("(max-width: 699px)");
    const measure = () => {
      const styles = getComputedStyle(element);
      const available = element.clientWidth - parseFloat(styles.paddingLeft) - parseFloat(styles.paddingRight);
      const variants = [...measurements.children] as HTMLElement[];
      const minimum = compact || phone.matches ? 1 : 0;
      const fit = variants.findIndex((sample, index) => index >= minimum && sample.getBoundingClientRect().width <= available);
      setStage(fit < 0 ? 4 : fit);
    };
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    observer.observe(measurements);
    phone.addEventListener("change", measure);
    document.fonts.addEventListener("loadingdone", measure);
    measure();
    return () => {
      observer.disconnect();
      phone.removeEventListener("change", measure);
      document.fonts.removeEventListener("loadingdone", measure);
    };
  }, [event, compact, failed]);

  const contents = (variant: number, measurement = false) => {
    const label = variant < 3 ? variant ? visual.code || visual.shortLabel : visual.shortLabel : "";
    return <>
      <SportIcon league={event.league} sport={event.sport} />
      {label && <span className="day-pill-league">{label}</span>}
      {label && (matchup || title) && <span className="day-pill-dot">·</span>}
      {matchup ? <span className="day-pill-matchup">
        {matchup.teams.map((team, index) => {
          const logo = Boolean(team.logo_url && !failed.has(team.logo_url));
          const names = variant < 4 || !logo;
          return <span className="day-pill-team" key={index}>
            {index > 0 && (variant < 4 || matchup.teams.some((item) => !item.logo_url || failed.has(item.logo_url))) &&
              <span className="day-pill-separator">{matchup.separator}</span>}
            {logo && <TeamLogo participant={team} load={!measurement} onError={() => onFailure(team.logo_url!)} />}
            {names && <span className="day-pill-name">{team.short_name || team.name}</span>}
          </span>;
        })}
      </span> : title && <span className={measurement ? "day-pill-title" : "pill-text"}>{title}</span>}
      {country && variant < 2 && <span className={measurement ? "day-pill-flag" : "country-flag"} role={measurement ? undefined : "img"} aria-label={measurement ? undefined : country.name}>{country.flag}</span>}
    </>;
  };
  return <><button {...props} aria-label={accessibleName} ref={root} className={`event-pill day-pill ${visual.className} ${className}`} data-detail={stage}>
    <span className="day-pill-line" aria-hidden="true">{contents(stage)}</span>
  </button><span className="day-pill-measurements" ref={samples} aria-hidden="true">
      {[0, 1, 2, 3, 4].map((variant) => <span className="day-pill-line" key={variant}>{contents(variant, true)}</span>)}
    </span></>;
}
