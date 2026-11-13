# GrantProof

Milestone-based grant payouts verified by GenLayer validators. A funder locks real GEN for one grantee and publishes, for every milestone, the public criteria, the GEN share, a time window and the URL prefixes that count as evidence. The grantee submits an evidence link per milestone, validators fetch the page themselves and must reach consensus on a verdict (APPROVED / REJECTED / UNDETERMINED). Only then does the share of that milestone become payable. Milestones the grantee never delivers can be clawed back by the funder, and anyone can challenge an approval before payout by staking a bond.

## What is different from AirdropGate

| | AirdropGate | GrantProof |
|---|---|---|
| Recipients | many strangers claim from one pool | one named grantee per grant |
| Criteria | one set per campaign | separate criteria and evidence prefixes per milestone |
| Order | independent claims | sequential milestones, the next one opens when the previous is paid |
| Payout | all-or-nothing reward per claim | partial payout, one share per milestone |
| Unused funds | sponsor reclaims after the claim window | funder claws back every undelivered milestone after its window |

## Three layers enforced in code

1. **Address anchor.** The grantee's own address must appear in the fetched evidence page, checked in deterministic code before any model call.
2. **Grounded verdict.** APPROVED is downgraded to UNDETERMINED unless the model returns an exact quote that really occurs in the fetched page.
3. **Bonded challenge.** The funder or any third party (never the grantee) can stake exactly 2 GEN against an approval before payout. The milestone is re-judged with the counter-evidence. An upheld challenge returns the bond plus a 10% bounty taken from that milestone's share and sends the milestone back to OPEN for a new submission. A failed or undetermined challenge never shortens the challenge window or blocks a later valid challenge (bounded to 2 restorations per submission); a failed one forfeits the bond to the grantee.

## Contract

`contracts/grantproof.py` (single file, deploy as is). Constructor argument: `min_window_seconds` (use `60` for testing, `3600` for production). Milestone numbers are 1-based. All GEN amounts are whole GEN.

| Method | Who | Purpose |
|---|---|---|
| `create_grant(title, grantee, challenge_window_seconds)` payable | funder | lock the budget in a DRAFT grant; invalid input is refunded to the caller's balance, not reverted |
| `add_milestone(grant_id, criteria, evidence_prefixes, amount_gen, due_seconds)` | funder | add a milestone to a draft; total shares must fit the budget |
| `activate_grant(grant_id)` | funder | start the grant, opens milestone 1, unallocated budget returns to the funder |
| `cancel_draft(grant_id)` | funder | cancel an unactivated draft and recover the whole budget |
| `submit_evidence(grant_id, milestone, evidence_url)` | grantee | submit a link for the open milestone before its deadline (3 submissions per milestone) |
| `evaluate_milestone(grant_id, milestone)` | anyone | consensus verification of the evidence page |
| `expire_submission(grant_id, milestone)` | anyone | reopen a milestone whose evaluation stalled for 3 days |
| `challenge_milestone(grant_id, milestone, counter_evidence_url)` payable, 2 GEN | anyone but the grantee | dispute an approval |
| `resolve_challenge(grant_id, milestone)` | anyone | consensus re-judgment with counter-evidence |
| `cancel_challenge(grant_id, milestone)` | anyone | refund a challenge that stayed unresolved for 3 days |
| `finalize_milestone(grant_id, milestone)` | anyone | pay an unchallenged approval and open the next milestone |
| `clawback(grant_id)` | funder | take back every missed or exhausted milestone and everything after it |
| `withdraw()` | anyone | pull payment of the caller's balance |

Views (all return JSON strings except `get_balance`): `get_params`, `get_stats`, `list_grants`, `get_grant`, `get_milestone`, `list_grants_by`, `get_balance`, `get_accounting`.

## Deployment

Deployed on GenLayer Studio; the contract address is listed in the latest GitHub release. The contract is submitted on its own, there is no frontend in this repository. The `evidence/` folder holds sample evidence pages used for live testing.

## Tests

```
python3 -m unittest discover -s tests -p "test_*.py"
```

No pip install is needed. The suite runs against a small offline stand-in for the GenLayer SDK (`tests/genlayer_stub.py`) and checks, after every call, that the contract's real GEN balance equals its recorded obligations. `tests/test_random_walk.py` runs 150 seeded random sequences of calls and then proves every grant reaches a terminal state and every deposited GEN can be withdrawn.

See `ARCHITECTURE.md` for the state machine, accounting and trust assumptions.

## License

MIT
