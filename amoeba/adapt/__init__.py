"""D117: adaptation inside one task (Box 4). After each plan step attempt plain code watches for stuck signals and names
one cause (stuck.py), tries code fixes cheapest first (fixes.py), and only then asks the fix proposer for one checked
edit (proposer.py); the edit menu with V1–V6 (recipe.py), the single-edit format (architect.py) and the hash-chained
event log (evidence.py) are kept from Phase 2. The offline learning loop of Phase 2 (Boxes 4–9) was removed by D117.
LLM proposes, plain code disposes."""
