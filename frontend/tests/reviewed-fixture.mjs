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
    return JSON.parse(readFileSync(join(directory, "2026.json"), "utf8"));
  } finally { rmSync(directory, { recursive: true }); }
}
