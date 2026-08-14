# GTM Agent Reply Copilot Deck Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Update the Deepline GTM Agent teardown deck with a first-principles framework and a responsive architecture diagram for a Lemlist Reply Copilot.

**Architecture:** Keep the artifact as one self-contained HTML file. Add semantic HTML/CSS components for the six-question framework and the workflow stages, plus an Excalidraw-sourced inline SVG diagram showing Lemlist → Deepline webhook → customer database → frontend agent and downstream actions. Reuse the deck's existing theme variables and make keyboard navigation advance exactly one slide per discrete keypress.

**Tech Stack:** Static HTML, CSS custom properties, inline SVG, vanilla JavaScript, browser rendering.

## Global Constraints

- Preserve the current deck's typography, palette, borders, slide proportions, theme behavior, keyboard navigation, and editorial tone.
- The workflow is specifically a Lemlist Reply Copilot.
- The MVP auto-drafts but does not auto-send; Slack approval is required before Lemlist sends.
- Deepline owns webhook receipt, the customer database, tools, state, and provenance. Slack is the human interface, HubSpot is CRM context and state, Notion is durable output storage, Lemlist is inbound and outbound email execution, and Vercel hosts only the frontend agent.
- Monitors appear only as a later trigger option.
- The page must remain self-contained and readable in light theme, dark theme, desktop width, and mobile width.

---

### Task 1: Replace the Pattern Slide With the Six-Question Framework

**Files:**
- Modify: `/Users/jaitoor/Downloads/Deepline-GTM-Agent-Teardown.html`

**Interfaces:**
- Consumes: Existing `.slide`, `.eyebrow`, heading, theme-variable, and responsive styles.
- Produces: `.principles`, `.principle`, `.q`, and `.answer` presentation classes used by slide 07.

- [ ] **Step 1: Record the current structural baseline**

Run:

```bash
node -e 'const fs=require("fs");const s=fs.readFileSync("/Users/jaitoor/Downloads/Deepline-GTM-Agent-Teardown.html","utf8");console.log({slides:(s.match(/<section class="slide/g)||[]).length,oldHeading:s.includes("Everyone built the same six things.")});'
```

Expected: the existing slide count is reported and `oldHeading` is `true`.

- [ ] **Step 2: Add framework styles and replace slide 07 content**

Add a two-column six-row framework whose exact question labels are `Who`, `When`, `What`, `How`, `Why`, and `Where`. The capability labels must be `Enrichment`, `Trigger`, `Tools · context`, `Tools · action`, `Filters / qualification`, and `Slack · CRM · custom app`.

- [ ] **Step 3: Verify the framework copy**

Run:

```bash
node -e 'const fs=require("fs");const s=fs.readFileSync("/Users/jaitoor/Downloads/Deepline-GTM-Agent-Teardown.html","utf8");for(const x of ["Every build needs the same six things.",">Who<",">When<",">What<",">How<",">Why<",">Where<"])if(!s.includes(x))throw new Error("missing "+x);console.log("framework ok")'
```

Expected: `framework ok`.

### Task 2: Add the Reply Copilot Architecture Slide

**Files:**
- Modify: `/Users/jaitoor/Downloads/Deepline-GTM-Agent-Teardown.html`

**Interfaces:**
- Consumes: The framework slide from Task 1 and the existing slide/navigation system.
- Produces: `.excalidraw-wrap`, `.excalidraw-map`, `.workflow-strip`, `.workflow-step`, `.runtime-call`, and inline SVG connector markup sourced from the Excalidraw scene.

- [ ] **Step 1: Add diagram and workflow styles**

Use existing CSS variables for color and borders. Add dedicated variables only for diagram fills that require light/dark theme variants. At `max-width:820px`, stack the system map and workflow into a vertical reading order without hiding nodes or connector meanings.

- [ ] **Step 2: Insert slide 08 before the existing MVP slide**

The slide must include:

```text
Lemlist reply → Deepline webhook → Customer DB
                                      ↓
                            Frontend agent (Vercel hosts)
                                      ↓
                           Slack approve / edit / reject
                                      ↓
                 Lemlist send + HubSpot log + Notion output
```

Show five workflow stages: `Reply arrives`, `Classify`, `Gather context`, `Draft + approve`, and `Send + learn`. List the classifications `positive`, `question`, `objection`, `not interested`, and `OOO`.

- [ ] **Step 3: Add the runtime recommendation**

Add a concise callout: Vercel hosts the frontend agent only; Deepline owns webhook receipt, customer data, connected tools, provenance, and the feedback loop.

- [ ] **Step 4: Verify required systems and safety boundary**

Run:

```bash
node -e 'const fs=require("fs");const s=fs.readFileSync("/Users/jaitoor/Downloads/Deepline-GTM-Agent-Teardown.html","utf8");for(const x of ["Slack","Vercel hosts only","Deepline webhook","Customer DB","HubSpot","Notion","Lemlist","approve","does not auto-send","Monitors later"])if(!s.includes(x))throw new Error("missing "+x);console.log("architecture ok")'
```

Expected: `architecture ok`.

### Task 3: Validate Structure and Rendering

**Files:**
- Verify: `/Users/jaitoor/Downloads/Deepline-GTM-Agent-Teardown.html`

**Interfaces:**
- Consumes: Completed self-contained deck from Tasks 1 and 2.
- Produces: Verified HTML with unchanged embedded teardown images and working navigation.

- [ ] **Step 1: Run structural assertions**

Run a Node assertion that the slide count increased by exactly one, the old heading is absent, the six questions occur in slide 07, the architecture slide occurs before the MVP slide, and the script still contains both ArrowRight and ArrowLeft handlers.

- [ ] **Step 2: Check markup balance and file integrity**

Run:

```bash
node -e 'const fs=require("fs");const s=fs.readFileSync("/Users/jaitoor/Downloads/Deepline-GTM-Agent-Teardown.html","utf8");for(const tag of ["section","div","svg"]) {const a=(s.match(new RegExp("<"+tag+"(?:\\\\s|>)","g"))||[]).length,b=(s.match(new RegExp("</"+tag+">","g"))||[]).length;if(a!==b)throw new Error(tag+" imbalance "+a+"/"+b)};console.log("markup balance ok",fs.statSync("/Users/jaitoor/Downloads/Deepline-GTM-Agent-Teardown.html").size)'
```

Expected: `markup balance ok` and a nonzero file size comparable to the original artifact.

- [ ] **Step 3: Render desktop and mobile screenshots**

Open the local file in a browser, inspect slide 07 and slide 08 at approximately 1440×1000 and 390×844, and verify there is no clipped text, overlapping connectors, horizontal overflow, or hidden system node.

- [ ] **Step 4: Inspect light and dark themes**

Toggle `data-theme="light"` and `data-theme="dark"` on the root element. Confirm text, connector labels, fills, and borders remain readable in both.

- [ ] **Step 5: Verify keyboard navigation**

Use ArrowRight and ArrowLeft across the new slide and confirm each discrete press moves exactly one slide, while repeated keydown events are ignored.
