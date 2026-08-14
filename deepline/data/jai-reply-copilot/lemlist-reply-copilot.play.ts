import { definePlay } from 'deepline';
import type { SqlListenerEvent } from 'deepline';

// Row shape delivered by lemlist.campaign_events / campaign_events. This is a starting
// point only: inspect the real columns with
//   deepline monitors available lemlist.campaign_events
// and tighten this type to the fields you read below.
//
// Before deploying a NEW monitor, run `deepline monitors list` — if one
// already feeds this stream for your scope, this play will already react to its
// rows (a play binds to the shared stream), so you may not need to deploy at all.
type MonitorRow = {
  delivery_id: string;
  event_type: string;
  [key: string]: unknown;
};

const FRONTEND_URL =
  'https://deepline-gtm-agent-production.up.railway.app/reply-copilot/events';

export default definePlay(
  "jai-lemlist-reply-copilot",
  async (ctx, event: SqlListenerEvent<MonitorRow>) => {
    // The monitor delivers the changed row as event.after. It is null for
    // DELETE operations, so guard before reading fields.
    const row = event.after;
    if (!row) {
      ctx.log(`Monitor ${event.tool}/${event.stream} ${event.operation} with no row; nothing to do.`);
      return { handled: false, operation: event.operation };
    }

    ctx.log(
      `Monitor ${event.tool}/${event.stream} ${event.operation}: ${JSON.stringify(row).slice(0, 200)}`,
    );

    if (row.event_type !== 'emailsReplied') {
      return { handled: false, operation: event.operation, reason: 'not_an_email_reply' };
    }

    const captured = await ctx.dataset('monitor_events', [row]).run({
      description: `Captured ${event.tool}/${event.stream} ${event.operation} rows.`,
    });

    const secret = ctx.secrets.get('REPLY_COPILOT_WEBHOOK_SECRET');
    const forwarded = await ctx.fetch(
      'forward_reply_to_frontend',
      FRONTEND_URL,
      {
        method: 'POST',
        auth: ctx.secrets.bearer(secret),
        headers: {
          'Content-Type': 'application/json',
          'Idempotency-Key': row.delivery_id,
        },
        body: JSON.stringify({ row }),
      },
    );

    if (!forwarded.ok) {
      throw new Error(`Reply frontend rejected event with HTTP ${forwarded.status}.`);
    }

    return {
      handled: true,
      tool: event.tool,
      stream: event.stream,
      operation: event.operation,
      changedAt: event.changedAt,
      capturedRows: await captured.count(),
      frontendStatus: forwarded.status,
    };
  },
  {
    description: "Run whenever lemlist.campaign_events writes a new campaign_events row.",
    // A monitor trigger: this play wakes on row changes written by the bound
    // monitor tool + stream. Discover a tool's streams and columns with:
    //   deepline monitors available lemlist.campaign_events
    // To bind a different monitor, swap tool/stream (and re-check operations)
    // for one of its (tool, stream) pairs.
    sqlListeners: [
      {
        id: 'events',
        tool: "lemlist.campaign_events",
        stream: "campaign_events",
        operations: ['INSERT'],
        where: { after: { event_type: { eq: 'emailsReplied' } } },
      },
    ],
    secrets: ['REPLY_COPILOT_WEBHOOK_SECRET'],
    billing: { maxCreditsPerRun: 2 },
  },
);
