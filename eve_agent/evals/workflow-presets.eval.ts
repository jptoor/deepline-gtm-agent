import { defineEval } from "eve/evals";
import { includes } from "eve/evals/expect";

export default defineEval({
  description: "Workflow presets are discoverable from the Eve agent.",
  tags: ["workflow-presets", "parity"],
  async test(t) {
    await t.send("List the available Deepline GTM workflow presets.");
    t.succeeded();
    t.calledTool("list_workflow_presets");
    t.check(t.reply, includes("web_context_research"));
    t.check(t.reply, includes("snowflake_query_agent"));
  },
});
