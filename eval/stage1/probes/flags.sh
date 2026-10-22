# Part 2 model setup for every run (sourced inside the runner container)
FLAGS=(--topology plan --llm openai --profile claude-sonnet+gemma-verify --routing routed --protocol v2
       --draft-prompts d24 --web-tools --plan-search on --adapt on --proposer scoped
       --pool --pool-dir /out/pool --local-tools on --local-tools-mode inprocess
       --max-tokens-per-run 5000000 --max-rate-retries 8 --ask-assumed off
       --timezone America/Chicago --niche general)
