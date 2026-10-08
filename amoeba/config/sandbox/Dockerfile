# D96: the image every agent sandbox boots (OpenShell docker driver, default_image amoeba-sandbox:local).
# Python with the office and data libraries the local tools use, Node and the same Claude Code version as the host
# (its `claude mcp serve` is the local-tool server, run inside the sandbox). No keys, no git config, no network at
# run time (the workload container runs with network=none). Build: docker build -t amoeba-sandbox:local .
FROM node:22-slim AS node
FROM python:3.11-slim
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
# (behind a TLS-inspecting build proxy, pass its CA as a build secret: --secret id=ca,src=<ca.crt>; it is used for the
# installs only and never stored in the image)
RUN --mount=type=secret,id=ca,required=false \
    export NODE_EXTRA_CA_CERTS=/run/secrets/ca PIP_CERT=/run/secrets/ca; \
    [ -s /run/secrets/ca ] || unset NODE_EXTRA_CA_CERTS PIP_CERT; \
    ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
 && npm install -g --no-fund --no-audit @anthropic-ai/claude-code@2.1.289 \
 && pip install --no-cache-dir openpyxl python-docx python-pptx matplotlib numpy pandas pypdf \
 && useradd -m -u 1000 -s /bin/bash sandbox \
 && rm -rf /root/.npm /root/.cache
# skills (the pool's clone, staged by build.sh) and Claude Code's managed settings (all hooks off) are root-owned and
# read-only for the sandbox user; the sandbox policy also lists them read-only
COPY skills/ /opt/skills/
COPY managed-settings.json /etc/claude-code/managed-settings.json
RUN chmod -R a-w,a+rX /opt/skills /etc/claude-code
ENV MPLBACKEND=Agg PYTHONDONTWRITEBYTECODE=1 LANG=C.UTF-8
USER 1000
WORKDIR /sandbox
