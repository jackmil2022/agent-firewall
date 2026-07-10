# Capability Repair Workbench Implementation Plan

## Product contract

Given an Agent, Skill, or MCP tool, the application runs repeatable tests in a
controlled workspace, records evidence, classifies failures, presents an
auditable change, and proves the change with the same test set before it can be
applied.

## Object model

- Agent: executable reasoning worker.
- Skill binding: instructions and resources attached to an Agent; not a flow step.
- Script action: an explicitly selected executable from a Skill.
- MCP server: connection and tool provider; not a flow step.
- MCP tool: discovered executable operation with an input schema.
- Assertion: deterministic acceptance rule.
- Approval: operator decision required before a protected operation.

## Delivery slices

### 1. Honest execution

- Apply all saved model preset fields at runtime.
- Discover MCP tools and schemas before configuring a call.
- Validate a flow before saving or running and return actionable issues.
- Prevent Skill bindings from being presented as executable Script actions.
- Accept an explicit run goal from the desktop application.

### 2. Repeatable test loop

- Store test cases, assertions, revisions, and run comparisons in SQLite.
- Run a target from a saved test case and evaluate deterministic assertions.
- Classify connection, discovery, selection, argument, execution, output,
  policy, and regression failures from recorded evidence.
- Save a successful baseline and compare a candidate run against it.

### 3. Auditable repair

- Produce before/after snapshots and a readable diff.
- Require explicit review before applying a revision.
- Preserve the previous snapshot and support revert.
- Re-run the same test case and record the comparison after a revision.

### 4. Desktop workflow

- Default to Test & Repair, with Capability Library, Runs, Policy, Settings,
  and Advanced Flow as peer views.
- Use a three-column test workspace: case, trace, diagnosis/change.
- Stream run events, show current target status, and allow cancellation.
- Replace generic resume with context-specific approval, retry, edit, apply,
  revert, and abandon actions.

### 5. Controlled distribution

- Route Agent, Script action, and MCP tool execution through one policy gate.
- Enforce workspace paths, command/network/environment rules, approvals,
  secret redaction, and audit events.
- Package a runnable Python backend with the Electron application.

## Verification gates

- Unit tests cover persistence, model resolution, preflight, assertions,
  diagnosis, revisions, policy enforcement, and run control.
- A headless Electron test creates a test case, runs a deterministic Script
  action, observes trace events, creates and reviews a revision, re-runs it,
  compares results, and reverts it.
- The packaged application starts without a project virtual environment and
  completes the deterministic smoke workflow.

