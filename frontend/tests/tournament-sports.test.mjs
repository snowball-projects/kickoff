import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { loadModule } from "./load-module.mjs";
import { publishedFiles } from "./published-fixture.mjs";

test("new tour and rugby metadata retain family identity and readable competition choices", async () => {
  const { interestGroups, leagueVisual, categoryForLeague } = await loadModule("calendar-helpers");
  const leagues = ["PGA_TOUR", "LPGA_TOUR", "DP_WORLD_TOUR", "LIV_GOLF", "ATP", "WTA", "SIX_NATIONS", "RUGBY_WORLD_CUP"];
  assert.deepEqual(interestGroups(leagues.map(value => ({ value }))), [
    { name: "Golf", leagues: leagues.slice(0,4) }, { name: "Tennis", leagues: ["ATP","WTA"] },
    { name: "Rugby", leagues: ["RUGBY_WORLD_CUP","SIX_NATIONS"] },
  ]);
  assert.equal(leagueVisual("DP_WORLD_TOUR").shortLabel, "DP World Tour");
  assert.equal(leagueVisual("SIX_NATIONS").className, "category-rugby");
  assert.equal(leagueVisual("ATP").className, "category-tennis");
  assert.equal(categoryForLeague("NEW_UNION_COMPETITION", "rugby"), "rugby");
  assert.equal(categoryForLeague("NEW_TOUR", "tennis"), "tennis");
});

test("flagged Grand Slams join the major tier while ordinary ATP/WTA tournaments stay below headline leagues", async () => {
  const { compareEvents } = await loadModule("calendar-helpers");
  const event = (event_id,league,competition_phase="regular_season") => ({event_id,title:event_id,league,competition_phase,start_time_utc:null});
  const sorted = [event("Regular ATP","ATP"),event("NFL","NFL"),event("WTA Grand Slam","WTA","championship"),
    event("PGA major","PGA_TOUR","championship"),event("ATP Grand Slam","ATP","championship"),event("Regular WTA","WTA")].sort(compareEvents);
  assert.deepEqual(sorted.map(row => row.event_id),["PGA major","ATP Grand Slam","WTA Grand Slam","NFL","Regular ATP","Regular WTA"]);
});

test("new golf tours use verified generic leaderboards; unsupported team match play stays source-only", async () => {
  const { leaderboardId, readLeaderboard } = await loadModule("golf");
  const fixture = JSON.parse(await readFile(new URL("./fixtures/golf-tours.json",import.meta.url),"utf8")).payloads;
  for (const [key,league] of [["dp_world","DP_WORLD_TOUR"],["liv","LIV_GOLF"]]) {
    const payload = fixture[key], id = payload.events[0].id;
    assert.equal(leaderboardId({sport:"golf",source:"espn",event_id:`espn-${league.toLowerCase()}-${id}`}),id);
    const board = readLeaderboard(payload,id,"America/Chicago",true);
    assert.equal(board.final,true);
    assert.equal(board.players.length,5);
    assert.equal(board.players[0].position,"1");
    assert(board.players.every(player=>player.name && player.total));
  }
  assert.equal(readLeaderboard(fixture.liv_matchplay,"401843581","UTC",false),null);
  assert.equal(leaderboardId({sport:"tennis",source:"espn",event_id:"espn-atp-154-2026"}),undefined);
});

test("tennis keeps inclusive calendar spans while DP/LIV expand into rounds across months in every viewer zone", async () => {
  const original = globalThis.fetch;
  try {
    const event = (event_id,league,sport) => ({event_id,league,sport,title:league,event_type:"tournament",source:"espn",
      calendar_date:"2026-01-30",end_calendar_date:"2026-02-02",start_time_utc:null,start_time_local:null,tags:[],competition_phase:"regular_season"});
    const files=publishedFiles([{season:2026,events:[event("ATP","ATP","tennis"),event("WTA","WTA","tennis"),
      event("DP","DP_WORLD_TOUR","golf"),event("LIV","LIV_GOLF","golf")]}]);
    globalThis.fetch=async url=>files[url.split("/").at(-1)]?Response.json(files[url.split("/").at(-1)]):new Response(null,{status:404});
    const { getCalendar }=await loadModule("data");
    const filters={sport:"",league:"",country:"",city:"",competition_phase:"",tags:[]};
    for(const zone of ["Pacific/Honolulu","Asia/Tokyo"]) {
      const months=await Promise.all(["2026-01-01","2026-02-01"].map(anchor=>getCalendar("month",2026,anchor,filters,zone)));
      const cards=months.flatMap(month=>month.groups.flatMap(group=>group.items));
      for(const league of ["ATP","WTA"]) {
        const selected=cards.filter(card=>card.league===league);
        assert.equal(selected.length,4);
        assert(selected.every(card=>card.title===league && card.start_calendar_date==="2026-01-30" && card.end_calendar_date==="2026-02-02"));
      }
      for(const league of ["DP_WORLD_TOUR","LIV_GOLF"])
        assert.deepEqual(cards.filter(card=>card.league===league).map(card=>card.round_or_stage),[1,2,3,4].map(n=>`Round ${n}`));
    }
  } finally {globalThis.fetch=original;}
});
