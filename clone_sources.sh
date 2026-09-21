#!/bin/bash
# Shallow-clone the source repos the Phase-1 spec cites (prompts are copied verbatim from these; MIT / Apache-2.0 / MIT).
set -e
mkdir -p repos && cd repos
[ -d AutoAgents ]  || git clone --depth 1 https://github.com/Link-AGI/AutoAgents.git
[ -d AgentVerse ]  || git clone --depth 1 https://github.com/OpenBMB/AgentVerse.git
[ -d jiuwen_atm ]  || git clone --depth 1 https://github.com/sidikbro/jiuwen_atm.git
echo "cloned. Line numbers in the spec were taken on 2026-09-20/21; if a file has moved, search for the quoted text."
