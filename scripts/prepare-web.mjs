import { readFile, mkdir, cp, readdir, rm } from "node:fs/promises";
import { createHash } from "node:crypto";
import { fileURLToPath } from "node:url";
import { join } from "node:path";
const root = fileURLToPath(new URL("../", import.meta.url));
const target = join(root, "frontend/public");
await mkdir(join(target, "data"), { recursive: true });
const names = (await readdir(join(root, "data/published"))).filter((n) => /^\d{4}\.json$/.test(n));
if (!names.length) throw Error("No reviewed public schedule snapshots");
const publishedNames = new Set(names);
for (const name of names) {
  const text = await readFile(join(root, "data/published", name), "utf8");
  const bundle = JSON.parse(text);
  if (bundle.schema_version !== "1" || !bundle.events?.length || !bundle.sources?.length || !bundle.updated_at)
    throw Error("Invalid public snapshot");
  if (/"(?:raw_source_payload|raw_artifacts|metadata|password|token|api_key)"\s*:/.test(text))
    throw Error("Private fields in public bundle");
  const ids = new Set();
  for (const event of bundle.events) {
    if (ids.has(event.event_id)) throw Error("Duplicate event");
    ids.add(event.event_id);
    if (["openfootball", "f1db"].includes(event.source)) {
      const repo = event.source === "f1db" ? "f1db/f1db" : "openfootball/football.json";
      const notice = bundle.sources.find((s) => s.url === `https://github.com/${repo}`);
      if (!/^[a-f0-9]{40}$/.test(notice?.revision || "") || !event.source_url?.startsWith(`https://github.com/${repo}/blob/${notice.revision}/`))
        throw Error("Missing pinned event provenance");
    } else if (["wikipedia", "wikidata"].includes(event.source)) {
      const notice = bundle.sources.find((s) => s.url === event.source_url && s.kind === event.source);
      const host = event.source === "wikipedia" ? "en.wikipedia.org" : "www.wikidata.org";
      const license = event.source === "wikipedia" ? "CC BY-SA 4.0" : "CC0 1.0";
      const url = new URL(event.source_url);
      if (!notice || notice.license !== license || url.protocol !== "https:" || url.hostname !== host || url.searchParams.get("oldid") !== String(notice.revision) || !/^[a-f0-9]{64}$/.test(notice.sha256) || !notice.changes || !notice.retrieved_at)
        throw Error("Missing reviewed Wikimedia provenance or license");
      const titles = url.searchParams.getAll("title");
      if (url.origin !== `https://${host}` || url.pathname !== "/w/index.php" || titles.length !== 1 || !titles[0] || (event.source === "wikidata" && !/^Q[1-9][0-9]*$/.test(titles[0])) || (event.source === "wikipedia" && /^(Wikipedia|File|Template|User|Category|MediaWiki|Help|Talk|Portal|Draft):/i.test(titles[0])))
        throw Error("Unreviewed Wikimedia article/entity namespace");
      if (event.start_time_utc || event.start_time_local || event.timezone || !event.end_calendar_date)
        throw Error("Reviewed date-only event has unsupported clock semantics");
      if (bundle.data_licenses?.[event.source] !== license)
        throw Error("Missing data license mapping");
    } else throw Error("Unreviewed public data source");
  }
  for (const kind of ["wikipedia", "wikidata"]) {
    const events = bundle.events.filter((e) => e.source === kind);
    if (!events.length) continue;
    const reference = bundle.components?.find((c) => new RegExp(`^${bundle.season}-${kind}-[a-f0-9]{64}\\.json$`).test(c.path));
    if (!reference) throw Error("Missing immutable licensed data component");
    const path = reference.path;
    publishedNames.add(path);
    const body = await readFile(join(root, "data/published", path));
    if (!reference || createHash("sha256").update(body).digest("hex") !== reference.sha256)
      throw Error("Missing or changed licensed data component");
    const component = JSON.parse(body);
    if (component.license !== bundle.data_licenses[kind] || !component.license_notice || JSON.stringify(component.events) !== JSON.stringify(events) || JSON.stringify(component.sources) !== JSON.stringify(bundle.sources.filter((s) => s.kind === kind)))
      throw Error("Data component diverges from attributed calendar");
    await cp(join(root, "data/published", path), join(target, "data", path));
  }
  await cp(join(root, "data/published", name), join(target, "data", name));
}
// Only these generated snapshot/component filenames are managed by this script.
for (const name of await readdir(join(target, "data"))) {
  if (/^\d{4}(?:-(?:wikipedia|wikidata)-[a-f0-9]{64})?\.json$/.test(name) && !publishedNames.has(name))
    await rm(join(target, "data", name));
}
for (const name of ["LICENSE", "THIRD-PARTY-NOTICES.txt"])
  await cp(join(root, name), join(target, name));
console.log(`Prepared ${names.length} reviewed public snapshot(s).`);
