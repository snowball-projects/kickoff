import { readFile } from "node:fs/promises";
import { stripTypeScriptTypes } from "node:module";
// Pure calendar modules have type-only imports; Node executes them without a
// development server, browser, network socket or dependency optimizer.
async function moduleUrl(name) {
  const source = await readFile(
    new URL(`../src/${name}.ts`, import.meta.url),
    "utf8",
  );
  let code = stripTypeScriptTypes(source, { mode: "strip" });
  for (const match of [...code.matchAll(/from "\.\/([^".]+)"/g)]) {
    const dependency = await moduleUrl(match[1]);
    code = code.replace(match[0], `from "${dependency}"`);
  }
  return `data:text/javascript;base64,${Buffer.from(code).toString("base64")}#${Math.random()}`;
}


export async function loadModule(name) { return import(await moduleUrl(name)); }
