import { defineEval } from "eve/evals";
import { includes } from "eve/evals/expect";

export default defineEval({
  description: "Eve app boots and can answer a simple non-tool greeting.",
  tags: ["smoke"],
  async test(t) {
    await t.send("Say ok in one word.");
    t.succeeded();
    t.check((t.reply ?? "").toLowerCase(), includes("ok"));
  },
});
