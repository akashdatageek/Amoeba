# Discarded runs

`h2-before-D84a/`: the first attempt at hypothesis h2 (the Assumptions planner rule), stopped after its first runs.
The section parser split the Planner's reply at a "##" in the middle of a line, so the Summariser role the Planner
wrote to follow the lesson was cut out of the roles JSON and lost (spec row D84a). These runs are kept as the
evidence of that bug; h2 was run again from the start with the fixed parser, and only that run is in the ledger.
