import { defineEval } from "eve/evals";
import { includes } from "eve/evals/expect";

export default defineEval({
  description: "Account research routes through Deepline and returns GTM-relevant output.",
  tags: ["parity", "research"],
  timeoutMs: 240_000,
  async test(t) {
    await t.send("Research stripe.com and summarize GTM-relevant signals.");
    t.succeeded();
    t.calledTool("deepline_chat");
    t.check((t.reply ?? "").toLowerCase(), includes("stripe"));
  },
});
