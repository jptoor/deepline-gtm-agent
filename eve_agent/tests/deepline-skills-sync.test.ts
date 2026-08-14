import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { createServer } from "node:http";
import { existsSync, mkdtempSync, readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { tmpdir } from "node:os";
import { resolve } from "node:path";
import test from "node:test";

const eveRoot = resolve(import.meta.dirname, "..");
const sourceIndexUrl = process.env.DEEPLINE_SKILLS_INDEX_URL;

test("Eve agent includes Deepline API well-known GTM skill package", () => {
  const skillPath = resolve(eveRoot, "agent/skills/deepline-gtm/SKILL.md");
  const recipePath = resolve(eveRoot, "agent/skills/build-tam/SKILL.md");

  assert.equal(existsSync(skillPath), true, "deepline-gtm skill should be copied");
  assert.equal(existsSync(recipePath), true, "recipe wrapper skills should be copied");

  const skill = readFileSync(skillPath, "utf8");
  assert.match(skill, /name:\s*deepline-gtm/);
  assert.match(skill, /GTM Meta Skill/);
  assert.match(skill, /provider-driven requests|provider\/quality defaults/);
});

test("committed Deepline skill snapshot matches well-known index API when available", async () => {
  if (!sourceIndexUrl) return;
  let source: {
    skills: Array<{ name: string; entrypoint: string; files?: string[] }>;
  };
  try {
    const response = await fetch(sourceIndexUrl, { signal: AbortSignal.timeout(5_000) });
    if (!response.ok) return;
    source = (await response.json()) as typeof source;
  } catch {
    return;
  }

  for (const skill of source.skills) {
    const targetPath = resolve(eveRoot, "agent/skills", skill.name, "SKILL.md");
    assert.equal(existsSync(targetPath), true, `${skill.name} should be copied`);
    for (const file of skill.files ?? []) {
      const copiedFile = resolve(eveRoot, "agent/skills", skill.name, file);
      assert.equal(existsSync(copiedFile), true, `${skill.name}/${file} should be copied`);
    }
  }
});

test("skill sync fetches from API and preserves hand-authored Eve skills", async () => {
  const tmp = mkdtempSync(resolve(tmpdir(), "eve-skill-sync-"));
  const skillsRoot = resolve(tmp, "agent/skills");
  mkdirSync(resolve(skillsRoot, "local_skill"), { recursive: true });
  writeFileSync(resolve(skillsRoot, "local_skill/SKILL.md"), "---\ndescription: local\n---\n# Local\n");
  mkdirSync(resolve(skillsRoot, "stale-generated"), { recursive: true });
  writeFileSync(resolve(skillsRoot, "stale-generated/.deepline-well-known-skill"), "old\n");
  writeFileSync(resolve(skillsRoot, "stale-generated/SKILL.md"), "---\ndescription: old\n---\n# Old\n");

  const server = createServer((request, response) => {
    const path = request.url ?? "";
    const bodies: Record<string, string> = {
      "/.well-known/skills/index.json": JSON.stringify({
        skills: [
          {
            name: "remote-skill",
            files: ["SKILL.md", "references/guide.md"],
          },
        ],
      }),
      "/.well-known/skills/remote-skill/SKILL.md":
        "---\nname: remote-skill\ndescription: Remote skill\ndisable-model-invocation: false\n---\n# Remote Skill\n",
      "/.well-known/skills/remote-skill/references/guide.md": "# Guide\n",
    };
    const body = bodies[path];
    if (body === undefined) {
      response.writeHead(404).end("not found");
      return;
    }
    response.writeHead(200, { "content-type": path.endsWith(".json") ? "application/json" : "text/plain" });
    response.end(body);
  });

  await new Promise<void>((resolveListen) => server.listen(0, "127.0.0.1", resolveListen));
  try {
    const address = server.address();
    assert.notEqual(address, null);
    assert.notEqual(typeof address, "string");
    if (!address || typeof address === "string") throw new Error("Expected TCP server address");
    const indexUrl = `http://127.0.0.1:${address.port}/.well-known/skills/index.json`;
    const result = await runScript(resolve(eveRoot, "node_modules/.bin/tsx"), [
      resolve(eveRoot, "scripts/sync-deepline-skills.ts"),
    ], {
      cwd: tmp,
      env: { ...process.env, DEEPLINE_SKILLS_INDEX_URL: indexUrl },
    });

    assert.equal(result.status, 0, result.stderr || result.stdout);
    assert.equal(existsSync(resolve(skillsRoot, "local_skill/SKILL.md")), true);
    assert.equal(existsSync(resolve(skillsRoot, "stale-generated/SKILL.md")), false);
    assert.equal(existsSync(resolve(skillsRoot, "remote-skill/SKILL.md")), true);
    assert.equal(existsSync(resolve(skillsRoot, "remote-skill/references/guide.md")), true);

    const copied = readFileSync(resolve(skillsRoot, "remote-skill/SKILL.md"), "utf8");
    assert.doesNotMatch(copied, /^disable-model-invocation:/m);
    assert.match(
      readFileSync(resolve(skillsRoot, "remote-skill/.deepline-well-known-skill"), "utf8"),
      /Source: http:\/\/127\.0\.0\.1:/,
    );
    assert.match(
      readFileSync(resolve(tmp, "agent/lib/deepline-skills-lock.ts"), "utf8"),
      /remote-skill/,
    );
  } finally {
    await new Promise<void>((resolveClose) => server.close(() => resolveClose()));
  }
});

test("skill sync check mode fails when committed generated files drift", async () => {
  const tmp = mkdtempSync(resolve(tmpdir(), "eve-skill-check-"));
  mkdirSync(resolve(tmp, "agent/skills"), { recursive: true });

  const server = createServer((request, response) => {
    const path = request.url ?? "";
    const bodies: Record<string, string> = {
      "/.well-known/skills/index.json": JSON.stringify({
        version: "test-version",
        generated_at: "2026-06-23T00:00:00.000Z",
        skills: [
          {
            name: "remote-skill",
            files: ["SKILL.md"],
          },
        ],
      }),
      "/.well-known/skills/remote-skill/SKILL.md":
        "---\nname: remote-skill\ndescription: Remote skill\n---\n# Remote Skill\n",
    };
    const body = bodies[path];
    if (body === undefined) {
      response.writeHead(404).end("not found");
      return;
    }
    response.writeHead(200, { "content-type": path.endsWith(".json") ? "application/json" : "text/plain" });
    response.end(body);
  });

  await new Promise<void>((resolveListen) => server.listen(0, "127.0.0.1", resolveListen));
  try {
    const address = server.address();
    assert.notEqual(address, null);
    assert.notEqual(typeof address, "string");
    if (!address || typeof address === "string") throw new Error("Expected TCP server address");
    const indexUrl = `http://127.0.0.1:${address.port}/.well-known/skills/index.json`;
    const script = resolve(eveRoot, "scripts/sync-deepline-skills.ts");

    const sync = await runScript(resolve(eveRoot, "node_modules/.bin/tsx"), [script], {
      cwd: tmp,
      env: { ...process.env, DEEPLINE_SKILLS_INDEX_URL: indexUrl },
    });
    assert.equal(sync.status, 0, sync.stderr || sync.stdout);

    const passingCheck = await runScript(resolve(eveRoot, "node_modules/.bin/tsx"), [script, "--check"], {
      cwd: tmp,
      env: { ...process.env, DEEPLINE_SKILLS_INDEX_URL: indexUrl },
    });
    assert.equal(passingCheck.status, 0, passingCheck.stderr || passingCheck.stdout);

    writeFileSync(resolve(tmp, "agent/skills/remote-skill/SKILL.md"), "tampered\n");
    const failingCheck = await runScript(resolve(eveRoot, "node_modules/.bin/tsx"), [script, "--check"], {
      cwd: tmp,
      env: { ...process.env, DEEPLINE_SKILLS_INDEX_URL: indexUrl },
    });
    assert.notEqual(failingCheck.status, 0);
    assert.match(failingCheck.stderr, /Skill snapshot is stale/);
  } finally {
    await new Promise<void>((resolveClose) => server.close(() => resolveClose()));
  }
});

async function runScript(
  command: string,
  args: string[],
  options: { cwd: string; env: NodeJS.ProcessEnv },
): Promise<{ status: number | null; stdout: string; stderr: string }> {
  return await new Promise((resolveRun, rejectRun) => {
    const child = spawn(command, args, options);
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (chunk) => {
      stdout += String(chunk);
    });
    child.stderr.on("data", (chunk) => {
      stderr += String(chunk);
    });
    child.on("error", rejectRun);
    child.on("close", (status) => resolveRun({ status, stdout, stderr }));
  });
}

test("copied Deepline skills are normalized for Eve authored-skill discovery", () => {
  const copiedSkillsRoot = resolve(eveRoot, "agent/skills");
  const copiedSkillNames = [
    "deepline-analytics",
    "deepline-feedback",
    "deepline-gtm",
    "deepline-plays",
    "deepline-quickstart",
    "niche-signal-discovery",
  ];

  for (const skillName of copiedSkillNames) {
    const skillPath = resolve(copiedSkillsRoot, skillName, "SKILL.md");
    assert.equal(existsSync(skillPath), true, `${skillName} should be copied`);
    const skill = readFileSync(skillPath, "utf8");
    assert.doesNotMatch(
      skill,
      /^disable-model-invocation:/m,
      `${skillName} should not include non-Eve frontmatter`,
    );
  }
});

test("copied Deepline skills preserve support documents needed by recipes", () => {
  for (const relativePath of [
    "deepline-gtm/finding-companies-and-contacts.md",
    "deepline-gtm/enriching-and-researching.md",
    "deepline-gtm/provider-playbooks/hunter.md",
    "deepline-gtm/provider-playbooks/salesforce.md",
    "deepline-gtm/recipes/linkedin-url-lookup.md",
    "deepline-gtm/scripts/validate-emails.py",
    "deepline-gtm/references/plays-sdk-reference.md",
    "deepline-gtm/references/plays-api-reference.md",
    "deepline-gtm/references/plays-run-export-inspect-repair.md",
  ]) {
    const targetPath = resolve(eveRoot, "agent/skills", relativePath);
    assert.equal(existsSync(targetPath), true, `${relativePath} should be preserved`);
  }
});
