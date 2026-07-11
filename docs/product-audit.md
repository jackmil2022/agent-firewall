# Agent Firewall Product Audit

## Verdict

The product direction is coherent if the primary promise is a capability test,
diagnosis, repair, and governance workbench for Agent, Skill, and MCP assets.
It is not yet a security firewall in the isolation sense. Process-level checks
and tool wrappers can govern declared operations, but they cannot prove that an
arbitrary Python process or model provider has no filesystem or network access.
Strong isolation requires a separate worker boundary such as a container, VM,
or platform sandbox.

The main product risk is therefore not the DAG editor. It is evidence quality:
the application must prove that the same versioned test, target, policy, model,
and environment were used before and after a repair.

## Primary User

The first user should be a capability author or platform operator who needs to:

1. Connect an Agent, Skill, or MCP server.
2. Discover the executable capability and inspect its contract.
3. Create repeatable test cases and deterministic assertions.
4. Run them under an explicit execution policy.
5. Diagnose the failing layer from recorded evidence.
6. Review a concrete candidate change.
7. Re-run the unchanged test snapshot and compare it with a successful baseline.
8. Apply or reject the change, then retain a reliable rollback path.

Trying to serve non-technical end users, capability authors, security reviewers,
and production operators in one first release will make the interface and the
trust model too broad.

## Product Object Model

- **Agent**: an executable reasoning configuration bound to a model and tools.
- **Skill binding**: instructions and resources available to an Agent; it is not
  executable by itself.
- **Script Action**: an explicitly selected executable inside a Skill.
- **MCP Server**: a connection and discovery source; it is not an execution target.
- **MCP Tool**: a discovered executable contract with server identity and schema.
- **Test Case**: a versioned target, input, assertion, and execution-profile snapshot.
- **Run**: immutable evidence for one Flow or Test Case execution.
- **Baseline**: an explicitly selected successful run for one immutable test snapshot.
- **Comparison**: a baseline/candidate result for the same snapshot.
- **Revision**: a before/after target snapshot linked to a reviewed passing comparison.
- **Policy**: the declared approval and resource rules used by a run.

## Information Architecture

The current top-level structure is appropriate:

- **Test & Repair** should remain the default work surface.
- **Capability Library** owns discovery, health, contracts, and provenance.
- **Runs** owns evidence, comparison, export, and retention.
- **Policy** owns execution profiles and approval rules.
- **Settings** owns model and connection configuration.
- **Advanced Flow** is a secondary expert tool, not the product home page.

The DAG editor should orchestrate already understood capabilities. It should not
be the place where users first discover whether a Skill or MCP Server is executable.

## Interaction Problems To Avoid

1. **Raw JSON as the primary form**: use MCP schemas and typed controls for common
   fields. Keep JSON as an advanced editor and show validation beside the field.
2. **Implicit baselines**: setting a baseline must be an explicit action on a
   successful run. Editing the case invalidates that baseline for comparison.
3. **Ambiguous continuation**: approval, correction, retry, and resume are distinct
   actions and must not share a generic "continue" button.
4. **Late-only feedback**: events should stream while a run is active, and cancel
   must have a defined final state rather than only closing the UI spinner.
5. **Server/tool confusion**: MCP discovery must produce Tool entries that retain
   their Agent, server, schema, and discovery version.
6. **Skill/action confusion**: a Skill is a binding. Only an explicitly selected
   Script Action may be executed or placed in a Flow.
7. **Unreviewable repair**: a repair needs a readable diff, affected tests, evidence,
   and a stale-target check before Apply is enabled.

## Trust And Architecture Gaps

### Strong isolation

Environment allowlists, command checks, and workspace path validation are useful
governance controls, but they are not a sandbox. A Script Action can open sockets
or access OS resources unless it runs in an isolated worker. The UI must describe
the current mode as governed local execution, not guaranteed containment.

### Reproducible evidence

Every Test Case run should snapshot or hash:

- test input and assertions;
- Agent config and model preset;
- Script content;
- MCP server identity, Tool schema, and arguments;
- policy and approval decision;
- relevant application/runtime versions.

Without these fields, a green comparison can be produced after changing the test
or target and is not regression proof.

### Policy coverage

Policy must wrap direct nodes, MCP discovery, MCP calls made from inside an Agent,
ACP entry points, and built-in tools. A policy that only checks the outer Agent
node is bypassable by nested tools.

### Secret handling

Redaction must occur before events, results, arguments, errors, and snapshots are
persisted. Display-time masking is insufficient because the SQLite database remains
an exfiltration source. Retention and export behavior also need explicit rules.

### Repair safety

Apply and Revert need optimistic concurrency checks. The current target must equal
the expected before/after snapshot, otherwise a stale revision can overwrite newer
work. Validation and the target write must be part of one transactional operation.

## Delivery Order

### P0: credible local workbench

- Independent packaged execution.
- Real model configuration and MCP discovery.
- Complete input propagation.
- Immutable test snapshots and explicit successful baselines.
- Structured assertions, diagnosis, events, and cancellation state.
- Reviewed revision linked to a passing comparison.
- Stale-safe apply and revert.

### P1: governed execution

- Policy wrappers for every entry point and nested tool.
- Environment minimization and secret redaction before persistence.
- Policy decision events and approval context.
- Typed MCP Tool forms generated from schemas.
- Import/export for test suites and evidence bundles.

### P2: security boundary and team governance

- Isolated worker runtime with enforceable filesystem/network limits.
- Signed capability packages and provenance.
- Roles, review ownership, retention, and shared registries.
- CI/headless evaluation and release gates.
- Version compatibility across MCP clients and model providers.

## Release Gate

A release is credible when a clean packaged application can discover a capability,
create a test, set a successful baseline, create and review a candidate revision,
run the exact same snapshot, record a passing comparison, apply the revision, and
revert it, while all policy decisions and redacted events remain auditable.
