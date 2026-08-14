# Jai Lemlist Reply Copilot

This workflow is intentionally split across Deepline and the thin frontend:

1. `lemlist-replies.monitor.json` captures every Lemlist `emailsReplied` event
   into `lemlist.lemlist_campaign_events` in Customer DB.
2. `lemlist-reply-copilot.play.ts` reacts to each inserted event and forwards
   the row to the deployed agent frontend over an authenticated webhook.
3. `managed_agent.reply_copilot` stores normalized state, gathers the complete
   Lemlist thread and Customer DB history, enriches company headcount, researches
   missing context, drafts in Jai's voice, and posts the Slack approval gate.
4. Slack Approve/Edit/Reject actions write their state and every edit back to
   `jai_reply_copilot.*` Customer DB tables.
5. Approve sends through Lemlist and logs the email in HubSpot only when
   `DEEPLINE_GTM_LIVE_WRITES=true`. The default is draft-only.

## Routing

- Company headcount > 50: meeting route.
- Company headcount <= 50: PLG promo route.
- Missing verified headcount: manual review with no inserted link.

## Required configuration

The same generated secret value must exist in both Railway and Deepline as
`REPLY_COPILOT_WEBHOOK_SECRET`.

Railway also needs:

- `REPLY_COPILOT_SLACK_CHANNEL_ID`
- `SLACK_BOT_TOKEN`
- `SLACK_SIGNING_SECRET`
- `REPLY_COPILOT_PROMO_URL`
- `REPLY_COPILOT_BOOKING_URL` (optional; the existing Calendly URL is defaulted)

Update the Slack app from `slack-manifest.json` so interactivity points at
`/reply-copilot/slack/interactions`.

## Safe rollout order

1. Run Python tests and `deepline plays check`.
2. Deploy the frontend with live writes disabled.
3. Create the Customer DB tables by calling `ReplyCopilotService.migrate()` once.
4. Set the shared webhook secret in Railway and Deepline.
5. Publish the listener play.
6. Deploy the Lemlist monitor after reviewing its dry-run.
7. Test one known reply and verify Slack edit logging before enabling sends.
