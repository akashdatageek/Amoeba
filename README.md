# Amoeba evidence branch

Evidence only, no code. Written by the Phase 2 loop harness (D95): each finished run that passed the key scan, and the
new rows of `eval/loop/<stream>/events.jsonl`, in the same layout as `eval/loop/<stream>/` on the code branches.

Every commit message carries the hash-chain head (the SHA-256 of the last event row of each stream it touches), so the
chain can be checked against this branch's history:

    python -m scripts.verify_evidence --branch evidence --stream <stream>

This branch is append-only: a ruleset blocks force-push and deletion.
