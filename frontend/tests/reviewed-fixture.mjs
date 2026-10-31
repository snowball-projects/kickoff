import { execFileSync } from "node:child_process";
import { existsSync, mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

export function reviewedBundle() {
  const root = fileURLToPath(new URL("../../", import.meta.url));
  const directory = mkdtempSync(join(tmpdir(), "kickoff-ui-"));
  try {
    const python = existsSync(join(root, ".venv/bin/python")) ? join(root, ".venv/bin/python") : "python";
    execFileSync(python, ["-m", "tests.frontend_fixtures", directory], { cwd: root });
    const index = JSON.parse(readFileSync(join(directory, "manifest.json"), "utf8"));
    const manifest = index.seasons["2026"];
    return { ...manifest, events: manifest.sports.flatMap(({ file }) =>
      JSON.parse(readFileSync(join(directory, file), "utf8")).events) };
  } finally { rmSync(directory, { recursive: true }); }
}
