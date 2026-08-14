import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import test from "node:test";
import { getWorkflowPreset, listWorkflowPresets } from "../agent/lib/workflow-presets.js";

test("workflow presets expose the same core preset ids as Python broker", () => {
  const ids = new Set(listWorkflowPresets().map((preset) => preset.id));
  for (const id of [
    "inbound_lead_approval",
    "account_digest",
    "self_serve_support_agent",
    "web_context_research",
    "account_brief",
    "signal_stacking",
    "org_chart_building",
    "bounded_tool_action",
    "closed_loop_gtm_workflow",
    "snowflake_query_agent",
  ]) {
    assert.equal(ids.has(id), true, `${id} should be listed`);
  }
});

test("web_context_research includes tool bounds and output shape", () => {
  const preset = getWorkflowPreset("web_context_research");
  assert.equal(preset?.speaker_pattern, "Exa / Scott Langille");
  assert.deepEqual(preset?.suggested_tool_bounds.enabledToolIds, ["deeplineagent", "firecrawl_search", "exa_search"]);
  assert.equal(preset?.suggested_tool_bounds.maxToolCalls, 6);
  assert.ok(preset?.expected_output.includes("source-backed claims"));
});

test("Prove workflow presets cover briefs, signal stacking, and org charts", () => {
  const accountBrief = getWorkflowPreset("account_brief");
  assert.equal(accountBrief?.title, "Rep-ready account brief");
  assert.ok(accountBrief?.expected_output.includes("first-message angle"));

  const signalStacking = getWorkflowPreset("signal_stacking");
  assert.equal(signalStacking?.suggested_tool_bounds.read_only, true);
  assert.ok(signalStacking?.expected_output.includes("anti-fit signals"));

  const orgChart = getWorkflowPreset("org_chart_building");
  assert.ok(orgChart?.best_for.includes("buying committee discovery"));
  assert.ok(orgChart?.human_approval_required_for.includes("Notion write"));
});

test("unknown workflow preset returns null", () => {
  assert.equal(getWorkflowPreset("nope"), null);
});

test("workflow presets include shared Deepline API onboarding recipes", () => {
  const presets = listWorkflowPresets();
  const sharedRecipe = presets.find((preset) => preset.id === "find_email");

  assert.ok(sharedRecipe, "find_email recipe should be listed");
  assert.equal(sharedRecipe.source, "deepline-api-recipe");
  assert.equal(sharedRecipe.title, "Waterfall Email Lookup");
  assert.ok(sharedRecipe.best_for.includes("primary"));
});

test("shared Deepline API recipes keep their prompt templates and defaults", () => {
  const preset = getWorkflowPreset("portfolio_scrape");

  assert.equal(preset?.source, "deepline-api-recipe");
  assert.equal(preset?.title, "VC Portfolio Scrape");
  assert.match(preset?.prompt ?? "", /Pull 5 companies from \{investor\}/);
  assert.deepEqual(preset?.slot_defaults, {
    investor: "Y Combinator W26",
    role: "Head of Marketing or VP Sales",
  });
  assert.ok(preset?.expected_output.includes("recipe prompt template"));
});

test("committed shared recipe snapshot matches deepline-api when available", () => {
  const deeplineApiRoot = resolve(
    process.env.DEEPLINE_API_REPO_PATH ?? "/Users/jaitoor/dev/deepline-api",
  );
  const sourcePath = resolve(deeplineApiRoot, "src/lib/onboard/recipes.json");
  if (!existsSync(sourcePath)) return;

  const source = JSON.parse(readFileSync(sourcePath, "utf8")) as {
    recipes: Array<{ id: string; title: string; promptTemplate: string }>;
  };
  const listed = new Map(listWorkflowPresets().map((preset) => [preset.id, preset]));

  for (const recipe of source.recipes) {
    const preset = listed.get(recipe.id);
    assert.ok(preset, `${recipe.id} should be listed from shared recipes`);
    assert.equal(preset.title, recipe.title);
    assert.equal(getWorkflowPreset(recipe.id)?.prompt, recipe.promptTemplate);
  }
});
