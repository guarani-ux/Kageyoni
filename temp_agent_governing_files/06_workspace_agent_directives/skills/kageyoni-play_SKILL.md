---
name: kageyoni-play
description: Run coordinated Kageyoni narrative scenes through the versioned world-state engine, including mixed combat, travel, discovery, training, social, and downtime actions with visibility-safe context and durable consequences.
---

# Kageyoni Play

Use this skill when the user wants to play, resume, or resolve a Kageyoni scene. Keep the fictional experience in the foreground while using the engine for supported mechanics and durable state.

## Locate the live project

Find the authoritative isolated development project and campaign database before acting. Prefer the delivered `kageyoni-local-dev` project and its declared campaign path. Do not open the original canonical `kageyoni-local` database for writes. Keep campaign state in the database, not in this skill directory. If more than one candidate exists, report the candidates and use the one whose manifest, runtime versions, and verification agree.

Open a session with the structured `session` operation. Check the selected branch, revision, runtime compatibility, visible context, pending consequences, and due or blocked processes. Use a GM viewer only for GM work. Use a participant viewer when preparing that participant's knowledge; never copy hidden facts into their context.

Call `opportunities` before presenting a constrained list of actions. Keep the explicit open action available. Do not turn relevance, rank, social advantage, or raw combat strength into a universal modifier.

## Resolve one intent

1. Read the scoped context for the actor, participants, targets, location, relationships, injuries, resources, political conditions, active processes, and deadlines.
2. Interpret the user's intent and record only bounded GM judgments that the engine cannot decide. Preserve independent NPC knowledge, priorities, refusals, and disagreement.
3. Select the relevant activity modules. For mixed situations, coordinate the modules into one resolution command. Read [references/domain-modules.md](references/domain-modules.md) when selecting modules.
4. Build a stable request ID and, when uncertainty is authorized, a stable roll ID. Use the command contract in [references/command-contract.md](references/command-contract.md).
5. Determine feasibility before uncertainty. Keep permission, probability, magnitude, cost, timing, and persistent consequences as separate stages. Use engine rules and property versions through stable identifiers; do not invent unresolved freedom, restrained-intelligence, Haki, or metaphysical mechanics.
6. Preview the exact command. If validation fails, repair the command without changing the intent. Apply the unchanged command only after the bounded judgment is settled.
7. On a stale revision, reread the branch and reconsider the action. On an uncertain response or repeated request, resend the same request ID and payload; do not roll again. A changed situation needs a new attempt ID and an explicit reason.
8. Read the committed receipt and affected context. Narrate the accepted result and its immediate fictional meaning. Mention a pending consequence or judgment when it is not yet resolved.

A d20 is one uncertainty component. Twenty is not the maximum total and never grants automatic success unless a versioned Kageyoni rule explicitly says so. A quiet competent action may resolve without a roll. Time advances only through an explicit fictional operation or a meaningful action that declares its clock and tick; chat messages, reloads, and real-world absence do not advance it.

For a Will technique, use `will-prepare` (or the `will_prepare` workflow)
with exact expression/technique versions, intent, targets, typed permission
checks, outcome bindings, and bounded judgments. The engine checks that the
actor bears the expression, evaluates mechanical preconditions before any
roll, pins the input snapshot and d20 result, and returns a durable attempt
reservation. Commit only with `will-apply`, using that unchanged reservation;
caller-supplied state deltas or altered outcomes are rejected. A proposed,
unavailable, out-of-scope, or judgment-bound technique does not silently
become an automatic success. See
[references/will-contract.md](references/will-contract.md).

## Information and agency

Use discovery and observation operations for what someone witnesses, then keep world fact, observation, belief, rumor, and institutional record separate. Visibility filters are part of the command. A hidden fact may affect a GM-authorized result without appearing in an unauthorized context.

Keep identity, nature, composition, agency, control, classification, capability, social role, chosen principles, Will capacity, Will mastery, learned mastery, power, and practical agency distinct. Do not assign a numerical freedom score unless a confirmed versioned rule exists. Preserve specific injuries, fatigue, memory disruption, recognition, and intention impairment instead of collapsing them into one health value.

## Consequences and time

Use structured consequences for mechanisms that are actually defined: a damaged route, a changed relationship, a political access condition, a resource shortage, a persistent technique effect, or a continuity disruption. Apply due work with `consequences` or `simulate`. If a consequence is free text, unsupported, contested, or requires judgment, preserve it as pending and say what judgment is needed. Do not create an external scheduler or claim an always-running simulation.

Do not let two modules charge the same cost, apply the same effect, or roll the same uncertainty. Do not use pacing to alter established dangers, NPC motives, deadlines, or outcomes. Stop compression at a meaningful decision point.

## Failure handling

Never write SQL during ordinary play. Use the engine CLI or its structured Python interface. Preserve the original event when correcting continuity, and attach causes and retained knowledge to a new correction or rewind event. If a command is rejected, explain the specific missing input or incompatible version. If processing is bounded, preserve and report the deferred work.
