import { readFileSync } from "node:fs";
import type { Page, Route } from "@playwright/test";
import { expect, test } from "./test";
import { event, setup } from "./fixtures";
const fixture = JSON.parse(readFileSync(new URL("../fixtures/fight-cards.json", import.meta.url), "utf8")).payloads;
const endpoint = /^https:\/\/site\.web\.api\.espn\.com\/apis\/site\/v2\/sports\/mma\/[^/]+\/scoreboard\?/;
const ufc = (id = "600061267", title = "UFC 333: Volkanovski vs. Evloev") => event(`espn-ufc-${id}`, "2026-10-24", {
  source: "espn", sport: "combat", league: "UFC", title, start_time_utc: "2026-10-24T14:00Z",
  source_url: `https://www.espn.com/mma/fightcenter/_/id/${id}/league/ufc`,
});
const fulfill = (route: Route, json: unknown) => route.fulfill({ json, headers: { "access-control-allow-origin": "*" } });
async function open(page: Page, name?: string) {
  await page.locator("#day-2026-10-24 .event-pill").click();
  if (name) await page.getByRole("button", { name: new RegExp(name) }).click();
}
async function mock(page: Page, payload = fixture.ufc) {
  const requests: string[] = [];
  await page.route(endpoint, async (route) => {
    const request = route.request();
    requests.push(request.url());
    expect(request.method()).toBe("GET");
    expect(request.postData()).toBeNull();
    expect(request.headers()["content-type"]).toBeUndefined();
    expect(request.headers().authorization).toBeUndefined();
    expect(Object.keys(request.headers()).some((name)=>name.startsWith("x-"))).toBe(false);
    await fulfill(route,payload);
  });
  return requests;
}
for (const width of [320,1280]) for (const colorScheme of ["light","dark"] as const) {
  test.describe(`fight cards ${width}px ${colorScheme}`,()=>{
    test.use({viewport:{width,height:844},colorScheme,reducedMotion:"reduce"});
    test("main event, records, weight, finished result, all real tabs and source",async({page})=>{
      const requests=await mock(page);
      await setup(page,[ufc()]);
      await open(page);
      const card=page.getByRole("region",{name:"Fight card",exact:true});
      await expect(card.getByRole("tab")).toHaveText(["Main card","Prelims","Early prelims"]);
      await expect(card.getByRole("tab",{name:"Main card",exact:true})).toHaveAttribute("aria-selected","true");
      const bouts=card.locator("li");
      await expect(bouts).toHaveCount(5);
      await expect(bouts.first()).toContainText("Alexander Volkanovski");
      await expect(bouts.first()).toContainText("29-4-0");
      await expect(bouts.first()).toContainText("Movsar Evloev");
      await expect(bouts.first()).toContainText("Featherweight");
      await expect(bouts.first()).toContainText("Final · R2 · 4:54");
      await expect(bouts.first().locator(".fight-fighter").first()).toContainText("Winner");
      await expect(card.locator(".fight-start")).toHaveText("1:00 PM");
      expect(requests).toEqual(["https://site.web.api.espn.com/apis/site/v2/sports/mma/ufc/scoreboard?dates=20261024"]);
      await expect(card.getByRole("link",{name:"Fight card · ESPN ↗"})).toHaveAttribute("href","https://www.espn.com/mma/fightcenter/_/id/600061267/league/ufc");
      await expect(card.locator(".fight-checked")).toHaveText("Checked 2026-10-28");
      for (const [name,count,first] of [["Prelims",4,"Dominick Reyes"],["Early prelims",5,"Colby Thicknesse"],["Main card",5,"Alexander Volkanovski"]] as const) {
        await card.getByRole("tab",{name,exact:true}).click();
        await expect(bouts).toHaveCount(count);
        await expect(bouts.first()).toContainText(first);
      }
      await card.getByRole("tab",{name:"Main card",exact:true}).focus();
      await page.keyboard.press("ArrowRight");
      await expect(card.getByRole("tab",{name:"Prelims",exact:true})).toBeFocused();
      await page.keyboard.press("Home");
      await expect(card.getByRole("tab",{name:"Main card",exact:true})).toBeFocused();
      expect(await page.getByRole("dialog").evaluate((el)=>el.scrollWidth<=el.clientWidth)).toBe(true);
      expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
      await card.scrollIntoViewIfNeeded();
      await page.screenshot({path:`test-results/fight-card-${width}-${colorScheme}.png`});
    });
  });
}

test.describe("fight card lifecycle",()=>{
  test.use({reducedMotion:"reduce"});
  for (const failure of ["http","json","wrong-event","network"]) test(`${failure} leaves schedule source without missing-data copy`,async({page})=>{
    let calls=0;
    await page.route(endpoint,async(route)=>{
      calls++;
      if(failure==="http") await route.fulfill({status:503,body:"unavailable",headers:{"access-control-allow-origin":"*"}});
      else if(failure==="json") await route.fulfill({body:"{",contentType:"application/json",headers:{"access-control-allow-origin":"*"}});
      else if(failure==="network") await route.abort();
      else await fulfill(route,fixture.pfl);
    });
    await setup(page,[ufc()]); await open(page);
    await expect.poll(()=>calls).toBe(1);
    await expect(page.getByRole("tablist")).toHaveCount(0);
    await expect(page.getByRole("link",{name:/Schedule source/})).toHaveAttribute("href",ufc().source_url);
    await expect(page.getByRole("dialog")).not.toContainText(/unavailable|missing|loading|undefined/i);
  });
  test("switching events resets segment and delayed old results cannot overwrite new card",async({page})=>{
    let release!:()=>void; const held=new Promise<void>((resolve)=>{release=resolve;});
    let started=false;
    const second={...ufc("600061420","UFC Fight Night: Moicano vs. Nolan"),start_time_utc:null};
    await page.route(endpoint,async(route)=>{
      if(!started){ started=true; await held; await fulfill(route,fixture.ufc).catch(()=>{}); }
      else await fulfill(route,{events:[...fixture.ufc.events,{...fixture.upcoming.events[0],date:"2026-10-24T21:00Z"}]});
    });
    await setup(page,[ufc(),second]); await open(page,"Volkanovski");
    await expect.poll(()=>started).toBe(true);
    await page.getByRole("button",{name:"Back to events"}).click();
    await page.getByRole("button",{name:/Moicano/}).click();
    await expect(page.getByRole("tabpanel")).toContainText("Renato Moicano");
    release();
    await expect(page.getByRole("tabpanel")).not.toContainText("Volkanovski");
    await expect(page.getByRole("tab")).toHaveText(["Main card","Prelims"]);
    await expect(page.getByRole("tabpanel")).not.toContainText("Winner");
    await page.getByRole("tab",{name:"Prelims",exact:true}).click();
    await page.getByRole("button",{name:"Back to events"}).click();
    await page.getByRole("button",{name:/Volkanovski/}).click();
    await expect(page.getByRole("tab",{name:"Main card",exact:true})).toHaveAttribute("aria-selected","true");
    await expect(page.getByRole("tabpanel")).toContainText("Alexander Volkanovski");
  });
  test("close aborts pending fetch and reopening only displays the new exact event",async({page})=>{
    let release!:()=>void; const held=new Promise<void>((resolve)=>{release=resolve;});
    let calls=0; let failed=false;
    page.on("requestfailed",(request)=>{if(endpoint.test(request.url())) failed=true;});
    await page.route(endpoint,async(route)=>{calls++; if(calls===1) {await held; await fulfill(route,fixture.ufc).catch(()=>{});} else await fulfill(route,{events:[{...fixture.upcoming.events[0],date:"2026-10-24T21:00Z"}]});});
    await setup(page,[ufc(),ufc("600061420","UFC Fight Night: Moicano vs. Nolan")]);
    await open(page,"Volkanovski"); await expect.poll(()=>calls).toBe(1);
    await page.getByRole("button",{name:"Close",exact:true}).click();
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await expect.poll(()=>failed).toBe(true);
    await open(page,"Moicano"); await expect(page.getByRole("tabpanel")).toContainText("Renato Moicano");
    release(); await expect(page.getByRole("tabpanel")).not.toContainText("Volkanovski");
    expect(calls).toBe(2);
  });
  test("PFL reviewed events match title and use the same live card; unsupported sports do not fetch",async({page})=>{
    const calls=await mock(page,fixture.pfl);
    const pfl=event("reviewed-pfl","2026-02-07",{sport:"mma",league:"PFL",title:"PFL Dubai: Nurmagomedov vs. Davis"});
    await setup(page,[pfl,event("Other","2026-02-07")],{now:"2026-02-07T17:00:00Z"});
    await page.locator("#day-2026-02-07 .event-pill").filter({hasText:"PFL"}).click();
    await expect(page.getByRole("tabpanel")).toContainText("Usman Nurmagomedov");
    expect(calls[0]).toContain("/mma/pfl/scoreboard?dates=20260207");
    await page.getByRole("button",{name:"Close",exact:true}).click();
    await page.locator("#day-2026-02-07 .event-pill").filter({hasText:"Premier League"}).click();
    await expect(page.getByRole("dialog")).toBeVisible();
    expect(calls).toHaveLength(1);
  });
  test("About privacy states MMA popups contact ESPN",async({page})=>{
    await setup(page,[ufc()]);
    await page.getByRole("button",{name:"About kickoff and schedule coverage"}).click();
    await expect(page.getByRole("region",{name:"Privacy",exact:true})).toContainText("MMA event popups contact ESPN");
  });
});
