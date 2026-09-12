# Devpost submission — Quiet Hours

**Track:** Everyday Agents
**Live demo:** https://quiet-hours-five.vercel.app
**Repo:** https://github.com/SebAustin/quiet-hours (Apache-2.0)

## Inspiration
Household admin never ends: bills, renewals, appointment recalls, school forms, deliveries that need a signature,
and the occasional "URGENT overdue invoice" that is really phishing. None of it is hard; all of it steals attention,
usually in the evening. We did not want another app to open. We wanted something that runs in the background and
only speaks up when there is a real decision to make.

## What it does
Quiet Hours is a household admin autopilot. On a schedule it reads the household's inbound stream, then:
- pays recurring bills that look normal, books appointments in the family's preferred window, fills recurring forms
  from the household profile, moves deliveries to a day someone is home, and blocks phishing;
- pauses for anything that is genuinely your call (a bill 81% above usual, an insurance premium up 18%, a form that
  needs your signature, a brand-new vendor) and sends you one decision card with the reason, on Slack and the dashboard;
- learns from every answer. "Approve and trust from now on" becomes a standing permission and a memory, so the same
  kind of item never interrupts you again. The dashboard shows interruptions falling day by day.

## How we built it
- **Strands Agents SDK**: a triage agent with structured output, one specialist agent per item with 13 custom tools,
  the `HumanInTheLoop` intervention driven by a deterministic **autonomy policy** as its classifier, and Strands
  **interrupts** to freeze the exact tool call. The paused agent's session is stored in S3, so the human can answer
  in a later invocation and the tool runs with the frozen arguments. Hooks write an audit trail with the policy reason.
- **Amazon Bedrock AgentCore**: Runtime (CodeZip), Memory (USER_PREFERENCE + SEMANTIC), Observability; deployed with the
  AgentCore CLI.
- **AWS**: EventBridge Scheduler → Lambda → `InvokeAgentRuntime`, DynamoDB single table, S3 sessions, Bedrock Nova
  (Claude-ready), SAM for infrastructure.
- **Dashboard**: Next.js on Vercel. Slack incoming webhook with HMAC-signed one-click links.

## Challenges
Making human-in-the-loop *durable*: an approval can arrive hours later, in a different process. Strands interrupts plus
a session manager gave us exactly that, and a small spike proved it before we built on it. The other challenge was
keeping the model honest: the policy, not the model, decides what may run unattended, and the payment tool refuses any
amount that does not match the bill.

## Accomplishments
A complete loop, deployed: scheduled sweeps on AgentCore, decision cards on Slack, one-tap resume, preferences in
AgentCore Memory, and a dashboard that shows the agent getting quieter over time.

## What we learned
Autonomy is a policy problem more than a prompting problem. Once every write is gated by explicit, testable rules and
every escalation carries its reason, people trust the agent enough to hand it more.

## What's next
Real inboxes and calendars through AgentCore Identity (Gmail, Google Calendar), bill-pay and scheduling integrations
behind AgentCore Gateway, per-member notification preferences, and a weekly "what I did" digest.
