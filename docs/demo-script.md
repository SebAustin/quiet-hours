# Demo video script (target 4:30)

## 0:00 – 0:35  The problem (slides or voiceover over the dashboard at day 0)
"Every household runs on a stream of small admin: bills, renewals, appointment recalls, school forms, deliveries.
None of it is hard. All of it costs attention, usually in the evening. Quiet Hours is an agent that handles the
routine in the background and only interrupts you for a real decision — and it learns from every answer."

Who it's for: busy parents and anyone who manages a home. Why it matters: hours of attention a month, and the
mistakes tired people make (paying the phishing invoice).

## 0:35 – 1:45  Day 1 (live)
1. Click **Next day** → seven items arrive (quiet meter shows seven grey tiles).
2. Click **Run sweep now** (about 20 s). Narrate while it runs: triage → one specialist per item → the autonomy
   policy gates every write tool.
3. Result: "3 handled quietly, 1 flagged, 3 need you." Point at the timeline: water bill paid ("within 25% of usual"),
   dentist booked Tuesday 15:30 (matches the family's window), UPS moved to Saturday morning, phishing invoice
   **blocked**, never paid.
4. Open a card: "Pay Austin Energy $214.37?" — the reason: "81% above the usual ~$118". Show Slack on the phone with
   the same card.

## 1:45 – 2:30  Decisions and learning
5. Tap **Approve and trust** on Austin Energy → the timeline entry appears with "you trusted this", and a standing
   permission appears: "pay bill for Austin Energy up to $246".
6. **Decline** the 18% insurance increase. **Approve** the field-trip form (signature + $12).
7. Under the hood: this is a Strands interrupt. The agent was frozen mid tool call in S3; the tap resumed the same
   session in a new AgentCore invocation and the tool ran with the exact frozen arguments. The answer is also written
   to AgentCore Memory.

## 2:30 – 3:30  Day 2 and 3
8. Next day → sweep. Spectrum paid, pediatrician booked. Two asks: Netflix price increase, a new piano teacher's
   invoice. **Trust** the piano teacher.
9. Next day → sweep. Piano invoice paid on its own ("you trusted pay_bill for Keys & Chords up to $138"), corrected
   electricity bill paid ("within 25% of usual"), FedEx moved to Saturday. One ask: soccer registration.
10. Trend chart: asked you 3 → 2 → 1 while handled quietly went up. "The agent gets quieter the longer it runs."

## 3:30 – 4:00  Ask Quiet Hours
11. Type "Why did you pay the piano invoice without asking?" → the chat agent explains from the audit log.

## 4:00 – 4:30  Architecture and close
12. Architecture slide: Strands agent on AgentCore Runtime, AgentCore Memory, DynamoDB + S3 sessions, EventBridge
    Scheduler → Lambda → Runtime, Slack, Next.js dashboard. CloudWatch trace of one sweep.
13. Close: "Quiet Hours: fewer pings every week, and every action explained."

## Recording tips
- Reset first: **Start over**, then reload. Keep Slack open on the phone (or a second window) for the card moment.
- Nova specialists take ~15–25 s per sweep; trim the wait in the edit.
