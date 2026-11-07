# GrantProof architecture

## Entities

- **Grant**: funder, grantee, title, locked budget, challenge window, 1-8 ordered milestones. Accounting: `remaining = budget - paid - bounty - refunded`.
- **Milestone**: public criteria, 1-5 evidence URL prefixes, GEN share, due window, submission and attempt counters, evidence history, challenge data.

Milestones are numbered from 1. The due window of a milestone starts when that milestone opens (activation for milestone 1, payment of the previous milestone for the others), so slow verification of one milestone never eats the time of the next.

## Grant state machine

```
create_grant -> DRAFT
DRAFT --add_milestone--> DRAFT
DRAFT --activate_grant--> ACTIVE (milestone 1 OPEN, unallocated budget refunded to the funder)
DRAFT --cancel_draft--> CANCELLED (whole budget refunded)
ACTIVE --every milestone PAID--> COMPLETED
ACTIVE --every milestone PAID or CLAWED_BACK, at least one clawed--> CLOSED
```

## Milestone state machine

```
WAITING --previous milestone PAID--> OPEN
OPEN --submit_evidence (grantee, before deadline, max 3)--> PENDING
PENDING --evaluate APPROVED--> APPROVED (challenge window starts)
PENDING --evaluate REJECTED--> OPEN
PENDING --evaluate UNDETERMINED--> PENDING (attempts+1; 3rd attempt -> OPEN)
PENDING --stale 3 days, expire_submission--> OPEN
APPROVED --challenge_milestone (once per submission, before challenge_end)--> CHALLENGED
APPROVED --finalize_milestone after challenge_end--> PAID (next milestone opens)
CHALLENGED --resolve REJECTED (upheld)--> OPEN (challenger gets bond + 10% of the share, the share shrinks by that bounty)
CHALLENGED --resolve APPROVED--> APPROVED, finalizable now (grantee gets the bond)
CHALLENGED --resolve UNDETERMINED--> APPROVED, finalizable now (bond refunded)
CHALLENGED --stale 3 days, cancel_challenge--> APPROVED, finalizable now (bond refunded)
OPEN --deadline passed or 3 submissions used, clawback--> CLAWED_BACK
WAITING --an earlier milestone was clawed back, clawback--> CLAWED_BACK
```

Every state has a path to a terminal state without trusting any single party:

- PENDING, CHALLENGED and APPROVED can be advanced by anyone.
- OPEN is either completed by the grantee or clawed back by the funder.
- DRAFT is cancelled by the funder, who is the only party with funds in it.

A milestone approved before its deadline keeps its right to be paid even if the finalization happens after the deadline; the deadline only limits submissions.

## Verification

`_evaluate` runs identically on the leader and every validator:

1. Fetch the evidence page (and the counter-evidence page for a challenge). A failed fetch is UNDETERMINED.
2. Deterministic anchor: the grantee address must occur in the page as a whole token (not inside a longer hex or alphanumeric string), otherwise REJECTED without any model call. The `===` marker sequence is neutralised in fetched text so a page cannot fake the prompt's section markers.
3. Ask the model for `{verdict, quote, reason}` against the criteria of that one milestone. The page text is declared untrusted in the prompt.
4. Grounding: APPROVED needs a quote of at least 12 characters that occurs in the page after whitespace normalisation, otherwise UNDETERMINED.

Consensus uses `gl.vm.run_nondet_unsafe(leader, validator)` with module-level functions (no contract `self` captured). The validator re-derives its own verdict and requires the same categorical verdict as the leader; the quote and reason are leader-attested. All errors are caught inside the nondet closures and turned into ordinary UNDETERMINED strings.

## Evidence URL rules

Evidence must be https, carry no credentials, use no non-443 port, contain no `..`, `%2e` or `%2f`, and, after lower-casing the host and dropping the fragment, start with one of the milestone's prefixes. Prefixes are validated when the milestone is added (https, end with `/`, no query). Look-alike hosts and `host@evil` forms are rejected by the parsed-URL checks.

## Money

All amounts are wei internally; users enter whole GEN (`amount_gen`, payable value). The attached value of `create_grant` must be a whole number of GEN. Payouts are pull-based: `finalize_milestone`, `clawback`, `activate_grant`, `cancel_draft` and the challenge outcomes only credit `balances`, `withdraw` transfers. Payable methods never revert on bad input; they credit the attached value back to the caller's balance. Invariant checked in tests after every call:

```
contract balance == sum(grant budget - paid - bounty - refunded) + sum(balances) + sum(open challenge bonds)
```

`get_accounting` exposes both sides. When a grant ends, `paid + bounty + refunded == budget` for it.

## Trust assumptions

- The funder is trusted to choose evidence prefixes under content they do not abuse. A prefix on a place where anyone can publish lets the grantee author their own proof; a prefix on pages only the funder controls lets the funder author counter-evidence. The grantee can read all criteria and prefixes with `get_grant` before doing any work.
- A funder who also controls the pages can shave at most the 10% bounty per upheld challenge, and the number of submissions per milestone is capped at 3.
- Validators are trusted only for the categorical verdict; code enforces anchoring, grounding, authorization, windows, ordering and accounting.

## Known limits

- One grantee per grant, up to 8 milestones, one challenge per submission.
- Time comes from `datetime.datetime.now()` as seen by GenVM.
- Evidence is judged from the text of one fetched page per submission.
