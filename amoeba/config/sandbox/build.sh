#!/bin/sh
# D96: build amoeba-sandbox:local. Stages the pool's skills clone into the build context (skills/, removed after).
# Behind a TLS-inspecting proxy set CA_BUNDLE=<ca.crt>; it is passed as a build secret, never stored in the image.
set -e
here="$(cd "$(dirname "$0")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
rm -rf "$here/skills" && mkdir -p "$here/skills"
src="$repo/data/pool/repos/anthropics_skills"
[ -d "$src" ] && (cd "$src" && tar --exclude=.git -cf - .) | (cd "$here/skills" && tar -xf -)
secret=""
[ -n "$CA_BUNDLE" ] && secret="--secret id=ca,src=$CA_BUNDLE"
docker build --network host $secret --build-arg HTTPS_PROXY --build-arg HTTP_PROXY --build-arg NO_PROXY \
  -t amoeba-sandbox:local "$here"
rm -rf "$here/skills"
