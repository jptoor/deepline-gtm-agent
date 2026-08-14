import { defineEval } from "eve/evals";
import { includes } from "eve/evals/expect";

export default defineEval({
  description: "Specialized GTM requests load the relevant Eve or copied Deepline skill before answering.",
  tags: ["skills", "parity"],
  timeoutMs: 240_000,
  async test(t) {
    await t.send("I want to update Salesforce contacts after enriching a prospect list. What should happen before writeback?");
    t.succeeded();
    t.calledTool("load_skill");
    const reply = (t.reply ?? "").toLowerCase();
    t.check(reply, includes("approval"));
    t.check(reply, includes("writeback"));
  },
});
