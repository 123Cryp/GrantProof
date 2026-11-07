import json
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_grantproof as T  # noqa: E402

stub = T.stub; mod = T.mod; WEI = T.WEI
ACTORS = [T.FUNDER, T.GRANTEE, T.BOB, T.CAROL, T.DAVE]
URLS = ["m1", "m2", "weak", "other", "revoked", "missing"]
def run(seed, steps=300):
    rnd = random.Random(seed)
    T.CLOCK[0] = 1_800_000_000
    h = stub.Harness(mod.GrantProof, T.FUNDER, 60)
    model = T.Model(); stub.chain.model = model
    for n in ("m1", "m2", "m3", "m1b", "m2b"): stub.chain.pages[T.url_for(n)] = T.good_page()
    stub.chain.pages[T.url_for("revoked")] = "Audit: the work of %s was REVOKED." % T.GRANTEE
    stub.chain.pages[T.url_for("weak")] = "Report by %s: still in progress." % T.GRANTEE
    stub.chain.pages[T.url_for("other")] = T.good_page(T.BOB)
    deposited = 0
    gids = []
    def acc():
        a = json.loads(h.contract.get_accounting())
        assert a["obligations"] == h.balance(), (seed, a, h.balance())
    for _ in range(steps):
        who = rnd.choice(ACTORS)
        g = rnd.choice(gids) if gids and rnd.random() < 0.9 else "g%d" % rnd.randint(1, 4)
        n = rnd.randint(1, 3) if rnd.random() < .9 else rnd.randint(0, 4)
        op = rnd.choice(["create", "add", "add", "act", "cancel", "submit", "submit", "eval", "eval", "expire",
                         "chal", "resolve", "cancelc", "final", "final", "claw", "withdraw", "time", "model", "eval", "submit", "final", "chal", "resolve"])
        try:
            if op == "create":
                v = rnd.choice([0, 1, 3, 7, 12]) * WEI + rnd.choice([0, 0, 0, 1])
                r = h.call(T.FUNDER if rnd.random() < .8 else who, "create_grant", "t", T.GRANTEE if rnd.random() < .9 else T.BOB, rnd.choice([60, 3600, 3600, 5]), value=v)
                deposited += v
                if r.startswith("g"): gids.append(r)
            elif op == "add":
                h.call(T.FUNDER if rnd.random() < .9 else who, "add_milestone", g, T.CRIT1, T.PREFIX, rnd.randint(0, 5), rnd.choice([60, 3600, 86400, 10]))
            elif op == "act": h.call(T.FUNDER if rnd.random() < .9 else who, "activate_grant", g)
            elif op == "cancel" and rnd.random() < .2: h.call(who, "cancel_draft", g)
            elif op == "submit": h.call(T.GRANTEE if rnd.random() < .9 else who, "submit_evidence", g, n, T.url_for(rnd.choice(URLS + ["m1", "m1", "m1b"])))
            elif op == "eval": h.call(who, "evaluate_milestone", g, n)
            elif op == "expire": h.call(who, "expire_submission", g, n)
            elif op == "chal":
                v = (2 if rnd.random() < .85 else rnd.choice([0, 1, 3])) * WEI
                deposited += v
                h.call(who, "challenge_milestone", g, n, T.url_for(rnd.choice(URLS + ["revoked", "revoked"])), value=v)
            elif op == "resolve": h.call(who, "resolve_challenge", g, n)
            elif op == "cancelc": h.call(who, "cancel_challenge", g, n)
            elif op == "final": h.call(who, "finalize_milestone", g, n)
            elif op == "claw": h.call(who, "claw" + "back", g) if who == T.FUNDER or rnd.random() < .3 else h.call(T.FUNDER, "clawback", g)
            elif op == "withdraw": h.call(who, "withdraw")
            elif op == "time": T.CLOCK[0] += rnd.choice([30, 30, 61, 61, 3601, 86401, 3 * 86400 + 5])
            elif op == "model":
                model.fixed = rnd.choice([None, None, {"verdict": "UNDETERMINED"}, {"verdict": "REJECTED"}, "junk"])
        except stub.NondetDisagreement:
            pass
        except Exception as e:
            if isinstance(e, (AssertionError, KeyError, TypeError, IndexError, AttributeError, ValueError, ZeroDivisionError)):
                raise
        acc()
    # drain: drive every grant to terminal using only permissionless/role paths
    model.fixed = None
    for _ in range(40):
        T.CLOCK[0] += 3 * 86400 + 5
        for gid in gids:
            gr = json.loads(h.contract.get_grant(gid))
            if gr["state"] == "DRAFT":
                h.call(T.FUNDER if gr["funder"].lower()==T.FUNDER.lower() else gr["funder"], "cancel_draft", gid); continue
            for m in gr["milestones"]:
                k = m["n"]
                for meth in ("expire_submission", "cancel_challenge", "finalize_milestone"):
                    try: h.call(T.DAVE, meth, gid, k)
                    except stub.NondetDisagreement: pass
                    except Exception as e:
                        if isinstance(e, (AssertionError, KeyError, TypeError, IndexError, AttributeError)): raise
            try: h.call(gr["funder"], "clawback", gid)
            except Exception as e:
                if isinstance(e, (AssertionError, KeyError, TypeError, IndexError, AttributeError)): raise
    for gid in gids:
        gr = json.loads(h.contract.get_grant(gid))
        assert gr["state"] in ("COMPLETED", "CLOSED", "CANCELLED"), (seed, gid, gr["state"], [m["state"] for m in gr["milestones"]])
        assert gr["remaining"] == 0, (seed, gr)
        assert gr["paid"] + gr["bounty"] + gr["refunded"] == gr["budget"]
    for who in ACTORS:
        if int(h.contract.get_balance(who)) > 0: h.call(who, "withdraw")
    assert h.balance() == 0, (seed, h.balance())
    assert sum(v for _, v in stub.chain.transfers) == deposited, (seed,)


class TestRandomWalk(unittest.TestCase):
    def test_random_walks_conserve_funds_and_never_get_stuck(self):
        for seed in range(150):
            run(seed)


if __name__ == "__main__":
    unittest.main(verbosity=2)
