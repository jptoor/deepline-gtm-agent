import { defineEval } from "eve/evals";
import { includes } from "eve/evals/expect";

export default defineEval({
  description: "Contact enrichment routes through Deepline.",
  tags: ["parity", "enrichment"],
  timeoutMs: 240_000,
  async test(t) {
    await t.send("Find the work email for Satya Nadella at microsoft.com");
    t.succeeded();
    t.calledTool("deepline_chat");
    t.check((t.reply ?? "").toLowerCase(), includes("microsoft"));
  },
});
