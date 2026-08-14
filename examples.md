# Example Prompts — Deepline GTM Agent

Copy-paste ready prompts for the most common GTM workflows.

---

## Workflow 1 — Inbound Lead Processing

Trigger: new signup, form fill, or CRM entry. Agent researches and drafts outreach.

```
New inbound lead just came in:
- Name: Sarah Chen
- Company: Figma
- Title: Head of Revenue Operations
- Email: sarah.chen@figma.com

Research this person and their company. Then draft a short (3-sentence) personalized
first email from our VP of Sales. Focus on what's relevant to her role specifically,
not generic copy. Include your confidence level and which sources you pulled from.
```

```
I have a list of new leads from last week's webinar. Start with the first one:
Marcus Williams, Director of Sales Ops at HubSpot (mwilliams@hubspot.com).

1. Verify the email
2. Research his background and what HubSpot is working on
3. Draft a 2-sentence personalized opener based on something specific to him or HubSpot right now
```

---

## Workflow 2 — Prospect Discovery + Enrichment

Trigger: SDR needs a list of target contacts for a new campaign.

```
Find 10 VP of Sales or Director of Sales at B2B SaaS companies:
- 100–500 employees
- Based in the US
- Not in the CRM already

For each one: full name, title, company, LinkedIn URL, and work email if available.
Tell me which ones have verified emails vs. which ones need more enrichment.
```

```
I'm targeting CFOs at fintech companies that recently raised Series B or C.
Find 5 of them, verify their emails, and for each one write one personalized sentence
I could use as an email opener (based on their company or role specifically).
```

```
Find the Head of Engineering or CTO at these companies:
- Rippling (rippling.com)
- Notion (notion.so)
- Linear (linear.app)

For each: LinkedIn URL, email (verified), and one signal about what they're working on
that I could reference in outreach.
```

---

## Workflow 3 — Recently Hired Contacts

Trigger: catch decision-makers who just started a new role — highest reply rates.

```
Find 5 VP of Sales who started a new job in the last 60 days at US SaaS companies.
I need their name, title, company, and LinkedIn URL.
```

```
Find GTM engineers or Revenue Operations leaders who were hired in the last 3 months.
Use recently_hired_months=3 when searching.
```

---

## Workflow 4 — Account Intelligence

Trigger: account review, QBR prep, renewal, or expansion motion.

```
Give me a quick account intelligence brief on Stripe (stripe.com):
- Current headcount and recent growth trend
- Key technologies in their stack
- What they're hiring for right now (signals for expansion or pain points)
- One paragraph on why a sales intelligence tool might matter to them specifically
```

```
I'm going into a call with Intercom tomorrow. Pull together:
1. Headcount (current + trend)
2. Tech stack highlights
3. Recent funding/news if available
4. 2–3 talking points tailored to their Head of Revenue profile
```

---

## Workflow 4.5 — Prove-Style Account Brief

Trigger: rep needs a concise point of view before a call or outbound touch.

```
Create a rep-ready account brief for Prove.

Buyer context:
- Team: GTM / RevOps
- Motion: outbound workflow automation

Return:
- company snapshot
- GTM motion
- current signals
- suspected pain
- Deepline angle
- first-message angle
- open questions
- sources and proof status

Keep it concise. Do not write to CRM or send outreach.
```

```
Create an account brief for a rep working ZeroClick.
Focus on why agent-purchasable APIs, x402, and new growth channels might matter.
Include only sourced claims, clear caveats, and one suggested reply angle.
```

---

## Workflow 4.6 — Signal Stacking

Trigger: rank accounts using multiple weak signals instead of one noisy trigger.

```
Score these accounts using signal stacking:
- Prove
- Persona
- Middesk
- Alloy

Separate:
- core fit
- buying intent
- infrastructure readiness
- anti-fit signals
- missing evidence

Return a 0-100 score, source-backed evidence, and the next safe workflow.
Do not enrich contacts or write to CRM without approval.
```

---

## Workflow 4.7 — Org Chart / Buying Committee

Trigger: enterprise rep needs a stakeholder map and multi-threading plan.

```
Build an org chart and buying committee map for Stripe.

Focus on:
- Sales
- RevOps
- Partnerships
- Security

Run a small discovery pass first. Mark inferred reporting lines clearly.
Include Deepline run IDs and source evidence. Do not run work-email enrichment
or write to Notion/CRM unless I approve it.
```

---

## Workflow 5 — Competitive Signal Monitoring

```
Research these 3 companies and tell me which one looks like the hottest prospect
right now based on hiring signals, growth, and tech stack:
- monday.com
- Asana
- ClickUp

Score them 1–10 on ICP fit and explain your reasoning.
```

```
Which of these companies is growing fastest right now?
- Rippling
- Deel
- Remote

Use headcount trends and recent funding signals. Show your sources.
```

---

## Workflow 6 — Email Personalization at Scale

```
I have 5 contacts to personalize outreach for. For each one, write a 1-sentence
personalized opener I can drop into a cold email template. Base it on something
specific (their role, their company's recent activity, or their LinkedIn).

1. Jenny Park, VP Sales at Rippling
2. Tom Nguyen, Head of RevOps at Notion
3. Alex Moore, Director of Sales at Linear
4. Rachel Kim, CTO at Retool
5. David Chen, VP Engineering at Figma

For each opener, note what signal you used and which data source it came from.
```

---

## Workflow 7 — Email Verification Before Send

```
Verify these emails and tell me which are safe to include in an outbound sequence:
- jsmith@salesforce.com
- m.johnson@hubspot.com
- alex@startupco.io
- ceo@bigcorp.com

For any that fail: tell me why (bounced, role-based, disposable, etc.) and
whether it's worth trying to find an alternative.
```

---

## Workflow 8 — Build a Target Account List

```
Build me a list of 20 B2B SaaS companies:
- 50–500 employees
- Headquartered in the US or Canada
- In the HR tech or people management space

For each: name, domain, headcount, and a one-line description of what they do.
I'll use this list to find contacts next.
```

```
Find me 15 fintech companies in New York with between 100 and 1000 employees.
I want to see their names, domains, headcount, and a brief description.
Flag any that look like they're in the payments or lending space specifically.
```

---

## Workflow 9 — CRM Operations

The agent has full read/write access to HubSpot, Salesforce, and Attio.

```
Search HubSpot for the contact john.smith@acme.com — show me all their details.
```

```
Create a new contact in HubSpot:
- Name: Jane Doe
- Email: jane.doe@techco.com
- Title: CTO
- Company: TechCo
```

```
Create a HubSpot deal called "Acme Corp - Enterprise" for $50,000.
Set it to the "Proposal Sent" stage.
```

```
Create a Salesforce lead for Marcus Williams, email mwilliams@bigco.com,
company BigCo, title VP of Sales.
```

```
Pull my last 10 Attio contacts.
```

---

## Workflow 10 — Outreach Campaign Management

The agent connects to Lemlist, Instantly, Smartlead, and HeyReach.

```
List all my Lemlist campaigns and their current stats.
```

```
Show me replies I've received in Lemlist in the last 7 days.
```

```
Show me all my Instantly campaigns and which ones are active.
```

```
What LinkedIn campaigns do I have running in HeyReach?
```

---

## Workflow 11 — C-Suite Lookup (web-first)

For C-suite titles, database providers often have stale data — the agent runs a live web search first.

```
Who is the current CEO and CRO of Rippling? Find their verified work emails.
```

```
Find the VP of Product at Linear. I need their LinkedIn URL and a verified email.
I'll be reaching out for a partnership conversation.
```

```
I want to reach the Head of Partnerships at Notion. Find them, verify their email,
and give me two sentences of context about their background I can reference.
```

---

## Tips

- **Be specific about company size, location, and title** — filters work best when they're precise. "VP of Sales at B2B SaaS, 200–500 employees, US" beats "sales leader at a tech company."
- **Chain workflows in one prompt** — "find 5 prospects, verify their emails, then draft openers" works in a single message. The agent calls tools in sequence.
- **For recently hired contacts** — ask explicitly: "hired in the last 60 days" or "started a new role in the last 3 months." The agent routes these to Icypeas which supports job start-date filtering.
- **Use location naturally** — "New York City", "NYC", "San Francisco", "London" all work. City-level searches route to Icypeas; country-level to Dropleads.
- **Start company research before contact search** — running `search_companies` first gives you domains, which makes `search_prospects` more precise.
- **For rep-facing workflows** — ask for the workflow by name: `account brief`, `signal stacking`, or `org chart`. These map to discoverable presets in the broker and Eve reference implementation.
- **For CRM and outreach** — just ask naturally. "Show me my Lemlist campaigns", "create a HubSpot contact", "pull Attio contacts" all route to the right integrations automatically.
