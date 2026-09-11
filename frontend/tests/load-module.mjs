import { readFile } from "node:fs/promises";
import { stripTypeScriptTypes } from "node:module";
// Pure calendar modules have type-only imports; Node executes them without a
// development server, browser, network socket or dependency optimizer.
export async function loadModule(name) {
  const source = await readFile(
    new URL(`../src/${name}.ts`, import.meta.url),
    "utf8",
  );
  const code = stripTypeScriptTypes(source, { mode: "strip" });
  return import(
    `data:text/javascript;base64,${Buffer.from(code).toString("base64")}#${Math.random()}`
  );
}
