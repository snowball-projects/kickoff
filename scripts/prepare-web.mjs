import { readFile, mkdir, cp, readdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { join } from "node:path";
const root = fileURLToPath(new URL("../", import.meta.url));
const target = join(root, "frontend/public");
await mkdir(join(target, "data"), { recursive: true });
const names = (await readdir(join(root, "data/published"))).filter((n) =>
  /^\d{4}\.json$/.test(n),
);
if (!names.length) throw Error("No reviewed public schedule snapshots");
for (const name of names) {
  const text = await readFile(join(root, "data/published", name), "utf8");
  const bundle = JSON.parse(text);
  if (
    bundle.schema_version !== "1" ||
    !bundle.events?.length ||
    !bundle.sources?.length ||
    !bundle.updated_at
  )
    throw Error("Invalid public snapshot");
  if (
    /"(?:raw_source_payload|raw_artifacts|metadata|password|token|api_key)"\s*:/.test(
      text,
    )
  )
    throw Error("Private fields in public bundle");
  const ids = new Set();
  for (const event of bundle.events) {
    if (ids.has(event.event_id)) throw Error("Duplicate event");
    ids.add(event.event_id);
    if (!["openfootball", "f1db"].includes(event.source))
      throw Error("Unreviewed public data source");
    if (
      !/^https:\/\/github.com\/(?:openfootball\/football.json|f1db\/f1db)\/blob\/[a-f0-9]{40}\//.test(
        event.source_url,
      )
    )
      throw Error("Missing pinned event provenance");
  }
  await cp(join(root, "data/published", name), join(target, "data", name));
}
for (const name of ["LICENSE", "THIRD-PARTY-NOTICES.txt"])
  await cp(join(root, name), join(target, name));
console.log(`Prepared ${names.length} reviewed public snapshot(s).`);
