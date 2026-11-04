import assert from "node:assert/strict";
import test from "node:test";
import { loadModule } from "./load-module.mjs";
const { dayPillTeams, dayPillTitle } = await loadModule("day-pill");
const home = { name: "Home source name", short_name: "Home", role: "home" };
const away = { name: "Away source name", short_name: "Away", role: "away" };
const event = { title: "Neutral-site source title", league: "EPL", sport: "soccer", participants: [home, away] };

test("day team ordering uses source roles and each sport's convention", () => {
  for (const sport of ["football", "american-football", "basketball", "baseball", "hockey"])
    assert.deepEqual(dayPillTeams({ ...event, sport }), { teams: [away, home], separator: "at" });
  for (const sport of ["soccer", "rugby", "cricket"])
    assert.deepEqual(dayPillTeams({ ...event, sport }), { teams: [home, away], separator: "vs" });
});
test("incomplete and roleless fixtures retain their exact source titles", () => {
  for (const participants of [[], [home], [away], [{ ...home, role: null }, { ...away, role: null }]]) {
    const fixture = { ...event, sport: "cricket", participants };
    assert.equal(dayPillTeams(fixture), null);
    assert.equal(dayPillTitle(fixture), event.title);
  }
});
test("individual event sessions remove only the competition's leading identity", () => {
  for (const [league, sport, title, expected] of [
    ["IWF_WORLDS", "weightlifting", "IWF Worlds · Women's 69 kg, Group D", "Women's 69 kg, Group D"],
    ["UFC", "combat", "UFC 325: Source names", "325: Source names"],
    ["ATP", "tennis", "Australian Open", "Australian Open"],
    ["PGA_TOUR", "golf", "The source tournament, Round 1", "The source tournament, Round 1"],
  ]) assert.equal(dayPillTitle({ ...event, league, sport, title }), expected);
});

test("day titles share the agenda's race and session semantics without duplicates", () => {
  for (const [fields, expected] of [
    [{ sport: "motorsport", league: "F1", event_type: "race", title: "F1 · Monaco Grand Prix" }, "Monaco Grand Prix · Race"],
    [{ sport: "motorsport", league: "F1", event_type: "race", title: "F1 · Monaco Grand Prix · Race" }, "Monaco Grand Prix · Race"],
    [{ sport: "weightlifting", league: "IWF_WORLDS", title: "IWF Worlds · Women's 69 kg", round_or_stage: "Group D" }, "Women's 69 kg · Group D"],
    [{ sport: "weightlifting", league: "IWF_WORLDS", title: "IWF Worlds · Women's 69 kg, Group D", round_or_stage: "Group D" }, "Women's 69 kg, Group D"],
    [{ sport: "golf", league: "PGA_TOUR", title: "The Open, Round 2", round_or_stage: "Round 2" }, "The Open, Round 2"],
  ]) assert.equal(dayPillTitle({ ...event, ...fields }), expected);
});
