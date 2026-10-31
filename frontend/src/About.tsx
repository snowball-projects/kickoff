import { timezoneLabel } from "./date-utils";
import type { ManifestResponse, SourceNotice } from "./types";

const PUBLISHERS: Record<string, string> = {
  world_climbing: "World Climbing", weightlifting: "Weightlifting federations", wikipedia: "Wikipedia",
};
function sourceGroups(sources: SourceNotice[]) {
  const groups = new Map<string, SourceNotice[]>();
  for (const source of sources) groups.set(source.kind, [...(groups.get(source.kind) || []), source]);
  return [...groups].map(([kind, items]) => {
    const pages = new Map<string, SourceNotice[]>();
    for (const source of items) pages.set(source.url, [...(pages.get(source.url) || []), source]);
    return { kind, name: PUBLISHERS[kind] || items[0].publisher || items[0].name, pages: [...pages.values()] };
  });
}
function Licenses({ sources }: { sources: SourceNotice[] }) {
  const links = [...new Map(sources.map((source) => [`${source.license_url}:${source.license}`, source])).values()];
  return links.map((source) => <span key={`${source.license_url}:${source.license}`}>{" · "}
    <a href={source.license_url} target="_blank" rel="noreferrer">{source.license}</a></span>);
}
export default function About({ manifest, timezone, storageNote }: {
  manifest?: ManifestResponse; timezone: string; storageNote: string;
}) {
  const updated = manifest?.updated_at?.slice(0, 10);
  return <div className="about">
    <p>A sports calendar by <a href="https://snowball-projects.github.io/">snowball</a>.</p>
    <p className="about-updated">{updated && <>Updated {updated}{" · "}</>}{timezoneLabel(timezone)}</p>
    <section aria-labelledby="about-coverage">
      <h3 id="about-coverage">Coverage</h3>
      <p>Published league schedules and reviewed motorsport, cycling, athletics, cricket, soccer, climbing, weightlifting and combat events. Dates and times can change.</p>
      <p>PGA Tour, LPGA Tour, DP World Tour and LIV Golf from ESPN. Rounds are all-day; past rounds show final tournament results when available.
        Tennis tournaments and rugby union schedules also come from ESPN.</p>
      <p>Boxing: Zuffa Boxing cards and reviewed men’s and women’s full WBA, WBC, IBF and WBO world title bouts.
        Title coverage excludes interim, regular/secondary and silver belts, regional titles and exhibitions.</p>
      <p><a href="https://github.com/snowball-projects/kickoff/tree/main/data/reviewed" target="_blank" rel="noreferrer">Coverage details ↗</a></p>
    </section>
    <section aria-labelledby="about-sources">
      <h3 id="about-sources">Sources</h3>
      {sourceGroups(manifest?.sources || []).map(({ kind, name, pages }) => <div className="about-source" key={kind}>
        {PUBLISHERS[kind] || kind.startsWith("boxing_") ? <details>
          <summary>{name}{" · "}<span>{pages.length} event {pages.length === 1 ? "page" : "pages"}</span></summary>
          <ul>{pages.map((sources) => <li key={sources[0].url}>
            <a href={sources[0].url} target="_blank" rel="noreferrer">{[...new Set(sources.map((source) => source.name))].join(" · ")}</a>
            <Licenses sources={sources} />
          </li>)}</ul>
        </details> : <p><a href={pages[0][0].url} target="_blank" rel="noreferrer">{name}</a><Licenses sources={pages.flat()} /></p>}
      </div>)}
      {manifest?.data_license_notice && <p className="about-license-notice">{manifest.data_license_notice}</p>}
    </section>
    <section aria-labelledby="about-privacy">
      <h3 id="about-privacy">Privacy</h3>
      <p>{storageNote || "Interests and options stay in this browser."} No accounts, analytics, advertising or location access.</p>
      <p>Timezone stays in your browser. Past and current agenda golf sections, golf event popups and MMA event popups contact ESPN. Active golf rounds refresh while visible.
        GitHub Pages receives hosting requests.</p>
    </section>
    <nav className="about-footer" aria-label="Project links">
      <a href="https://github.com/snowball-projects/kickoff" target="_blank" rel="noreferrer">Source</a>{" · "}
      <a href={`${import.meta.env.BASE_URL}THIRD-PARTY-NOTICES.md`}>Licenses</a>{" · "}
      <a href="https://snowball-projects.github.io/operations/#kickoff">Operations</a>
    </nav>
  </div>;
}
