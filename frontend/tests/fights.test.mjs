import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { loadModule } from "./load-module.mjs";
const { fightCardRequest, readFightCard } = await loadModule("fights");
const fixture = JSON.parse(readFileSync(new URL("./fixtures/fight-cards.json", import.meta.url), "utf8")).payloads;
const event = { event_id: "espn-ufc-600061267", source: "espn", league: "UFC", title: "UFC 333: Volkanovski vs. Evloev", calendar_date: "2026-10-24", start_time_utc: "2026-10-24T14:00Z" };
const request = fightCardRequest(event);

test("live UFC fixture groups only distinct start times and reverses source bout order, main event first", () => {
  const before = JSON.stringify(fixture.ufc);
  const card = readFightCard(fixture.ufc, request);
  assert.deepEqual(card.blocks.map((b) => [b.label,b.bouts.length]), [["Main card",5],["Prelims",4],["Early prelims",5]]);
  assert.deepEqual(card.blocks[0].bouts[0].fighters, [
    { id:"3949584",name:"Alexander Volkanovski",record:"29-4-0",winner:true },
    { id:"4029275",name:"Movsar Evloev",record:"20-1-0",winner:false },
  ]);
  assert.equal(card.blocks[0].bouts[0].weight,"Featherweight");
  assert.equal(card.blocks[0].bouts[0].result,"Final · R2 · 4:54");
  assert.equal(card.blocks[0].bouts[1].fighters[0].name,"Petr Yan");
  assert.equal(card.sourceUrl,"https://www.espn.com/mma/fightcenter/_/id/600061267/league/ufc");
  assert.equal(JSON.stringify(fixture.ufc),before);
});

test("two-block current card has no Early prelims and scheduled main card has no results", () => {
  const card = readFightCard(fixture.upcoming,{...request,id:"600061420",date:"2026-10-31"});
  assert.deepEqual(card.blocks.map((b)=>b.label),["Main card","Prelims"]);
  assert.equal(card.blocks[0].bouts[0].fighters[0].name,"Renato Moicano");
  assert(card.blocks[0].bouts.every((b)=>b.result==="" && b.fighters.every((f)=>!f.winner)));
});

test("PFL reviewed title matches exactly with case and whitespace normalized, never by date alone", () => {
  const pfl = fightCardRequest({...event,event_id:"reviewed-pfl",source:"wikipedia",league:"PFL",title:" pfl dubai: Nurmagomedov vs. Davis ",start_time_utc:null,calendar_date:"2026-02-07"});
  assert.equal(pfl.url,"https://site.web.api.espn.com/apis/site/v2/sports/mma/pfl/scoreboard?dates=20260207");
  const card = readFightCard(fixture.pfl,pfl);
  assert.equal(card.blocks.flatMap((b)=>b.bouts).length,13);
  assert.equal(card.blocks[0].bouts[0].fighters[0].name,"Usman Nurmagomedov");
  assert.equal(readFightCard(fixture.pfl,{...pfl,title:"PFL Dubai: Other vs. Fighters"}),null);
  assert.equal(readFightCard({events:[...fixture.pfl.events,...fixture.pfl.events]},pfl),null);
});

test("exact ESPN id can be anywhere in a shared-date scoreboard; wrong ids never fall back to title", () => {
  const payload={events:[...fixture.pfl.events,...fixture.ufc.events]};
  assert.equal(readFightCard(payload,request).blocks[0].bouts[0].fighters[0].name,"Alexander Volkanovski");
  assert.equal(readFightCard(payload,{...request,id:"wrong"}),null);
  assert.equal(readFightCard(payload,{...request,date:"2026-10-25"}),null);
  for(const value of [{},null,{events:[]}]) assert.equal(readFightCard(value,request),null);
});

test("ONE's sparse scoreboard retains its one real bout without inventing weight or extra segments", () => {
  const card=readFightCard(fixture.one,{...request,id:"600060243",promotion:"ofc",date:"2026-02-27"});
  assert.deepEqual(card.blocks.map((b)=>b.label),["Main card"]);
  assert.equal(card.blocks[0].bouts[0].weight,"");
  assert.equal(card.blocks[0].bouts[0].fighters[1].name,"Sardor Karimboev");
});

test("malformed bouts are skipped without mutating valid bouts or fabricating start blocks", () => {
  const payload=structuredClone(fixture.ufc);
  payload.events[0].competitions[0].date="2026-10-24T14:00";
  payload.events[0].competitions[1].competitors.pop();
  payload.events[0].competitions[2].competitors[0].athlete={};
  const card=readFightCard(payload,request);
  assert.equal(card.blocks.flatMap((b)=>b.bouts).length,11);
  assert.equal(readFightCard({events:[{id:request.id,competitions:[]}]},request),null);
});

test("scoreboard date follows ESPN Eastern day across UTC midnight regardless of viewer calendar date", () => {
  assert.equal(fightCardRequest({...event,start_time_utc:"2026-06-28T00:00Z",calendar_date:"2026-06-28"}).date,"2026-06-27");
  assert.equal(fightCardRequest({...event,start_time_utc:null,calendar_date:"2026-06-27"}).date,"2026-06-27");
  assert.equal(fightCardRequest({...event,league:"NFL"}),null);
  assert.equal(fightCardRequest({...event,start_time_utc:null,calendar_date:null}),null);
});
