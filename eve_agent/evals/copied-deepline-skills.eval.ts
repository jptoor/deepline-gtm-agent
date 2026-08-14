import { defineEval } from "eve/evals";
import { includes } from "eve/evals/expect";

export default defineEval({
  description: "A copied Deepline well-known skill can be loaded for GTM recipe routing.",
  tags: ["skills", "deepline-well-known"],
  timeoutMs: 240_000,
  async test(t) {
    await t.send("Use the Deepline GTM workflow for LinkedIn URL lookup. What guidance should you load before running it?");
    t.succeeded();
    t.calledTool("load_skill");
    const reply = (t.reply ?? "").toLowerCase();
    t.check(reply, includes("deepline"));
    t.check(reply, includes("linkedin"));
  },
});
