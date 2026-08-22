/**
 * A script to sync the exact linter dependencies
 * from `./bun.lock` to `../.pre-commit-config.yaml`
 */

import { readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

interface BunLock {
  packages: Record<string, [string, ...unknown[]]>;
}

const script_dir = join(fileURLToPath(import.meta.url), "..");
const lock_path = join(script_dir, "bun.lock");

const config_path = join(script_dir, "..", ".pre-commit-config.yaml");

/**
 * Strip JSONC trailing commas so `JSON.parse` accepts a `bun.lock`.
 *
 * bun writes trailing commas, which every strict parser rejects — both
 * `JSON.parse` and `Bun.file().json()`. Commas are only dropped when the next
 * non-whitespace character closes the enclosing object or array, and string
 * literals are skipped, so a comma inside a package name or version range can
 * never be mistaken for a structural one.
 */
function strip_trailing_commas(text: string): string {
  let out = "";
  let in_string = false;
  let escaped = false;
  for (let i = 0; i < text.length; i += 1) {
    const ch = text[i] ?? "";
    if (in_string) {
      out += ch;
      if (escaped) {
        escaped = false;
      } else if (ch === "\\") {
        escaped = true;
      } else if (ch === '"') {
        in_string = false;
      }
      continue;
    }
    if (ch === '"') {
      in_string = true;
      out += ch;
      continue;
    }
    if (ch === ",") {
      let j = i + 1;
      while (j < text.length && /\s/.test(text[j] ?? "")) {
        j += 1;
      }
      const next = text[j];
      if (next === "}" || next === "]") {
        continue;
      }
    }
    out += ch;
  }
  return out;
}

async function main() {
  const lock_content = await readFile(lock_path, "utf-8");
  const bun_lock = JSON.parse(strip_trailing_commas(lock_content)) as BunLock;
  const packages = bun_lock.packages;

  const current_config = await readFile(config_path, "utf-8");
  let new_config = current_config;

  for (const [name, info] of Object.entries(packages)) {
    // info[0] is "package@version"
    const version = info[0].split("@").pop();
    if (name !== "" && version !== undefined && version !== "") {
      new_config = new_config.replaceAll(
        new RegExp(`"${name}@[\\d\\.]+"`, "g"),
        `"${name}@${version}"`,
      );
    }
  }

  if (new_config !== current_config) {
    console.log("Writing updated pre-commit config.");
    await writeFile(config_path, new_config, "utf-8");
  }
}

main().catch((e: unknown) => {
  console.error(e);
  // Without this the script exits 0 on failure, so a parse error looked like a
  // successful no-op and the pre-commit version pins silently stopped syncing.
  process.exitCode = 1;
});
