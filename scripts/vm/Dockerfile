# D172: the throwaway RUNNER container for real runs with Box 4's scoped round. Inside it, local tools run in-process
# (AMOEBA_SANDBOX=1, --local-tools-mode inprocess), so a probe's workspace files can be undone and the scoped round
# never falls back to single (it does in the OpenShell sandbox). The container itself is the sandbox: it holds the
# repository, the Python libraries, LibreOffice, scipy, pytest, Node and Claude Code (whose `claude mcp serve` is the
# local-tool server), and nothing of the host. No key is in the image: run.sh passes them from the environment, and
# mounts only one output folder. Build from the repository root:
#     docker build -f scripts/vm/Dockerfile -t amoeba-runner:local .
ARG BASE_REGISTRY=docker.io/library
FROM ${BASE_REGISTRY}/node:22-slim AS node
FROM ${BASE_REGISTRY}/python:3.11-slim
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
# (behind a TLS-inspecting build proxy, pass its CA as a build secret: --secret id=ca,src=<ca.crt>; used for the
# installs only, never stored in the image)
RUN --mount=type=secret,id=ca,required=false \
    export NODE_EXTRA_CA_CERTS=/run/secrets/ca PIP_CERT=/run/secrets/ca; \
    [ -s /run/secrets/ca ] || unset NODE_EXTRA_CA_CERTS PIP_CERT; \
    ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
 && npm install -g --no-fund --no-audit @anthropic-ai/claude-code@2.1.289 \
 && apt="apt-get ${PIP_CERT:+-o Acquire::https::CAInfo=$PIP_CERT}" \
 && $apt update -qq && $apt install -y --no-install-recommends libreoffice-calc libreoffice-writer git \
 && rm -rf /var/lib/apt/lists/* /root/.npm
WORKDIR /amoeba
COPY . /amoeba
# the same libraries as the agent sandbox (D158: numpy, pandas, scipy, matplotlib, pillow, openpyxl, python-docx,
# python-pptx, pypdf, pytest), then Amoeba itself (pip install -e: the sandbox bridge imports the package)
RUN --mount=type=secret,id=ca,required=false \
    export PIP_CERT=/run/secrets/ca; [ -s /run/secrets/ca ] || unset PIP_CERT; \
    pip install --no-cache-dir -r amoeba/config/sandbox/libs.txt scipy pytest \
 && pip install --no-cache-dir -e ".[test,local]" \
 && rm -rf /root/.cache runs data/lessons \
 && useradd -m -u 1000 -s /bin/bash runner && chown -R runner /amoeba
ENV AMOEBA_SANDBOX=1 MPLBACKEND=Agg PYTHONDONTWRITEBYTECODE=1 LANG=C.UTF-8
USER 1000
ENTRYPOINT ["/bin/bash", "-lc"]
CMD ["python -m scripts.preflight --mode inprocess"]
