# Agents for Humans: building Quiet Hours, a household autopilot that only interrupts you for real decisions

*(Draft for builder.aws.com — publish before the deadline for bonus points. Title keeps "Agents for Humans".)*

Every evening, the same small pile: a water bill, a dentist recall, a permission slip, a delivery that needs a
signature, and one "URGENT" invoice from a domain that is almost, but not quite, the power company's. For the
Agents for Humans hackathon I built **Quiet Hours**, an agent that clears that pile in the background and only
surfaces the decisions that are genuinely mine.

## The design idea: interruptions are the product
Most agent demos maximise what the agent does. This one minimises what the human sees. Three rules shaped it:
1. Every write action passes through a deterministic **autonomy policy** before it runs.
2. Anything the policy will not sign off becomes a **decision card**: one tap, with the reason.
3. Every answer is **remembered**, so the agent gets quieter every week.

## Strands made the hard part small
Strands Agents ships a `HumanInTheLoop` intervention that pauses the agent before a tool call and lets you plug in a
classifier. My classifier is 120 lines of plain Python: recurring vendor within 25% of usual and under the cap →
proceed; new vendor, price jump above 10%, form with a signature, suspicious sender → pause.

The pause is a Strands **interrupt**. The magic is that the interrupt survives the process: with `S3SessionManager`
the specialist's state is parked in S3, and hours later a Lambda invokes AgentCore Runtime again with the human's
answer. The agent resumes and the tool runs with the *exact* arguments it proposed. No second round of reasoning, a
clean audit trail, and "trust from now on" can be scoped to that tool, vendor and amount.

```python
agent = Agent(
    model=model, tools=tools.all_tools,
    interventions=[HumanInTheLoop(allowed_tools=READ_TOOLS, classifier=policy.classify, enable_trust=True)],
    hooks=[audit], session_manager=S3SessionManager(session_id=f"item-{item.id}", bucket=bucket),
)
result = await agent.invoke_async(prompt)
if result.stop_reason == "interrupt":   # → decision card + Slack
    ...
# later, in another invocation:
agent([{"interruptResponse": {"interruptId": card.interrupt_id, "response": "t"}}])
```

## AgentCore did the plumbing
`agentcore create`, `agentcore add memory`, `agentcore deploy`. Runtime hosts the agent, Memory learns preferences
from the decision events, Observability gives me a trace per sweep. EventBridge Scheduler calls a small Lambda that
calls `InvokeAgentRuntime`; DynamoDB holds items, actions and cards; Slack gets HMAC-signed one-click links.

## What I'd tell another builder
- Spike the risky mechanic first. My first hour was a two-process interrupt/resume test. Everything else was built on
  a proven foundation.
- Let policy, not prompts, decide autonomy. Test it like code.
- Show the reason with every interruption. It is the difference between "the bot pinged me" and "the bot is careful".

Repo: https://github.com/SebAustin/quiet-hours · Demo: https://quiet-hours-five.vercel.app
