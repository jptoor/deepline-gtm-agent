import { defineEval } from "eve/evals";
import { includes } from "eve/evals/expect";

export default defineEval({
  description: "Risky workflows preserve pilot, approval, and writeback guidance.",
  tags: ["parity", "approval"],
  timeoutMs: 240_000,
  async test(t) {
    await t.send("Build a CSV prospect list of 20 VP Sales contacts and write approved updates back to Salesforce.");
    t.succeeded();
    t.calledTool("deepline_chat");
    const reply = (t.reply ?? "").toLowerCase();
    t.check(reply, includes("approval"));
    t.check(reply, includes("pilot"));
  },
});
