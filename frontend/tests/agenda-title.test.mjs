import assert from "node:assert/strict";
import test from "node:test";
import { loadModule } from "./load-module.mjs";

// Title identities checked against the published bundles on 2026-10-31:
// https://snowball-projects.github.io/kickoff/data/2026.json
// https://snowball-projects.github.io/kickoff/data/2027.json
const examples = [
  ["IWF_WORLDS", "IWF World Championships · Men's 75 kg, Group C", "Men's 75 kg, Group C"],
  ["IWF_JUNIOR_WORLDS", "IWF World Junior Championships · Men's 60 kg, Group A", "Men's 60 kg, Group A"],
  ["IWF_YOUTH_WORLDS", "IWF World Youth Championships · Men's 56 kg", "Men's 56 kg"],
  ["MASTERS_WORLDS", "World Masters Weightlifting Championships · Men's M35 110 kg, Group A · Platform A - BLUE", "Men's M35 110 kg, Group A · Platform A - BLUE"],
  ...["African", "Asian", "European", "Pan-American"].map((name, i) => [
    ["WEIGHTLIFTING_AFRICA", "WEIGHTLIFTING_ASIA", "WEIGHTLIFTING_EUROPE", "WEIGHTLIFTING_PAN_AMERICA"][i],
    `${name} Weightlifting Championships · Men's 60 kg`, "Men's 60 kg",
  ]),
  ["WEIGHTLIFTING_OCEANIA", "Oceania Championships / Universal Weightlifting Cup · Men's 60 kg", "Universal Weightlifting Cup · Men's 60 kg"],
  ["WEIGHTLIFTING_OCEANIA", "Pacific Games / Oceania Senior Championships", "Pacific Games / Oceania Senior Championships"],
  ["WEIGHTLIFTING_COMMONWEALTH_GAMES", "Commonwealth Games weightlifting · Men's 60 kg", "Men's 60 kg"],
  ["WEIGHTLIFTING_ASIAN_GAMES", "Asian Games weightlifting · Men's 60 kg", "Men's 60 kg"],
  ["WEIGHTLIFTING_PAN_AM_GAMES", "Pan American Games weightlifting", ""],
  ["NASCAR_CUP", "NASCAR Cup Series at Martinsville", "Martinsville"],
  ["NASCAR_CUP", "NASCAR Cup Series All Star Race", "All Star Race"],
  ["NASCAR_CUP", "Clash at Bowman Gray", "Clash at Bowman Gray"],
  ["UFC", "UFC 336: Van vs. Kape", "336: Van vs. Kape"],
  ["UFC", "UFC Fight Night: Dallas", "Fight Night: Dallas"],
  ["UFC", "Dana White's Contender Series: Season 10, Week 1", "Dana White's Contender Series: Season 10, Week 1"],
  ["PFL", "PFL Austin: Eblen vs. Kasanganay 2", "Austin: Eblen vs. Kasanganay 2"],
  ["RIZIN", "Rizin Landmark 13", "Landmark 13"],
  ["ONE", "ONE Fight Night 39: Rambolek vs. Dayakaev", "Fight Night 39: Rambolek vs. Dayakaev"],
  ["IFSC_WORLD_CUP", "World Cup · Gunsan · Boulder Qualification", "Gunsan · Boulder Qualification"],
  ["IFSC_WORLD_CUP", "Alcobendas · Men's Boulder Final", "Alcobendas · Men's Boulder Final"],
  ["IFSC_WORLDS", "World Championships · Brno", "Brno"],
  ["IFSC_YOUTH_WORLDS", "Youth World Championships · Jamshedpur", "Jamshedpur"],
  ["IFSC_PARA_WORLDS", "Para World Championships · Brno", "Brno"],
  ["IFSC_PARA_WORLD_CUP", "Para World Cup · Catania", "Catania"],
  ["CLIMBING_EUROPE", "European Youth Championships · Augsburg · Men's U17 Lead Final", "Youth · Augsburg · Men's U17 Lead Final"],
  ["CLIMBING_EUROPE", "European Para Championships · Geneva", "Para · Geneva"],
  ["CLIMBING_ASIA", "Asian Championships · Meishan · Men's Boulder Final", "Meishan · Men's Boulder Final"],
  ["CLIMBING_OCEANIA", "Oceania Championships · Mount Maunganui · Speed Final", "Mount Maunganui · Speed Final"],
  ["CLIMBING_PAN_AMERICA", "Pan American Championships · Curitiba · Men's Speed Final", "Curitiba · Men's Speed Final"],
  ["CLIMBING_CHALLENGER", "World Climbing Challenger Shanghai · Men's Speed Final", "Shanghai · Men's Speed Final"],
  ["CLIMBING_NATIONS_GRAND_FINALE", "World Climbing Nations Grand Finale Fukuoka · Lead Mixed Team Final", "Fukuoka · Lead Mixed Team Final"],
  ["CLIMBING_ASIAN_GAMES", "Asian Games Aichi-Nagoya · Men's Speed Final", "Aichi-Nagoya · Men's Speed Final"],
  ["CLIMBING_ASIAN_BEACH_GAMES", "Asian Beach Games Sanya", "Sanya"],
  ["CLIMBING_EUROPEAN_GAMES", "European Games · Istanbul", "Istanbul"],
  ["CLIMBING_SOUTH_AM_GAMES", "South American Games · Santa Fe · Men's Lead Final", "Santa Fe · Men's Lead Final"],
  ["CLIMBING_PAN_AM_GAMES", "Pan American Games · Lima", "Lima"],
  ["CLIMBING_CONTINENTAL_CUP", "World Climbing Asia Series Gunsan · Boulder Qualification", "Asia Series Gunsan · Boulder Qualification"],
  ["CLIMBING_YOUTH_CONTINENTAL_CUP", "World Climbing Europe Youth Series Dornbirn · Men's U17 Lead Final", "Europe Youth Series Dornbirn · Men's U17 Lead Final"],
  ["CLIMBING_OLYMPIC_QUALIFIERS", "World Climbing Africa Qualifier", "Africa Qualifier"],
  ["PGA_TOUR", "THE PLAYERS Championship", "THE PLAYERS Championship"],
  ["LPGA_TOUR", "Blue Bay LPGA", "Blue Bay LPGA"],
  ["F1", "Mexico Grand Prix · Practice 1", "Mexico Grand Prix · Practice 1"],
  ["INDYCAR", "Grand Prix of Indianapolis (Road Course)", "Grand Prix of Indianapolis (Road Course)"],
];

test("one title rule preserves event-specific facts across published competition identities", async () => {
  const { agendaEventTitle } = await loadModule("agenda-title");
  for (const [league, title, expected] of examples) {
    const event = { league, title, sport: "", city: null, venue: null };
    assert.equal(agendaEventTitle(event), expected, `${league}: ${title}`);
    assert.equal(event.title, title, "the original popup title stays intact");
  }
});

test("every league uses the header identity, with word boundaries and conservative matching", async () => {
  const { agendaEventTitle } = await loadModule("agenda-title");
  const { leagueVisual } = await loadModule("calendar-helpers");
  const leagues = [...new Set([...examples.map(([league]) => league),
    "NFL", "NBA", "MLB", "NHL", "EPL", "BUNDESLIGA", "LA_LIGA", "SERIE_A", "LIGUE_1", "CHAMPIONSHIP",
    "EREDIVISIE", "PRIMEIRA_LIGA", "BRASILEIRAO", "UEFA_CHAMPIONS_LEAGUE", "FIFA_WORLD_CUP", "BOXING_MAJOR",
  ])];
  for (const league of [...leagues, "FUTURE_LEAGUE"]) {
    const label = leagueVisual(league).shortLabel;
    assert.equal(agendaEventTitle({ league, title: `${label} · Final` }), "Final", league);
    assert.equal(agendaEventTitle({ league, title: `${label}ville Final` }), `${label}ville Final`, league);
    assert.equal(agendaEventTitle({ league, title: `Final at ${label}` }), `Final at ${label}`, league);
  }
  assert.equal(agendaEventTitle({ league: "UFC", title: "UFC", city: "Paris", venue: "Arena" }), "Paris");
  assert.equal(agendaEventTitle({ league: "UFC", title: "UFC", venue: "Arena" }), "Arena");
  assert.equal(agendaEventTitle({ league: "UFC", title: "UFC" }), "");
  assert.equal(agendaEventTitle({ league: "ONE", title: "Someone at ONE" }), "Someone at ONE");
});
