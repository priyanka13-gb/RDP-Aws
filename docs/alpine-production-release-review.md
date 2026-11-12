# Alpine production promotion — Task 21

2026-11-06: **GO for code review; NO-GO for publishing this uncommitted build.**
The production Dockerfile now exactly matches the passing Task 20 Alpine recipe.
No commit, push, AWS deployment, Terraform operation or credential change occurred.

## Implementation and support

Changed `app/Dockerfile`: two stages, dependencies installed in the matching musl
builder and copied into `/opt/python`, pip removed from the runtime, numeric
UID/GID 10001, existing Uvicorn command and port 8000 preserved. The runtime still
contains apk and a shell; it is not distroless. No application dependencies or
application source were changed. Existing CA certificates remain available.

Both stages use the evaluated official Python 3.12 Alpine base:

```text
python@sha256:e064671ca452259bab50e8e2c7bd896e39e9a343bb06ca25234adf6fe18d0fc7
```

Observed versions: Python 3.12.16, Alpine 3.24.4, musl 1.2.6-r3.
[Python 3.12 security support](https://devguide.python.org/versions/) runs through
October 2028. [Alpine 3.24 main support](https://alpinelinux.org/releases/) runs
through 2028-06-01; community support has a shorter lifecycle. Follow the earliest
applicable support deadline and refresh pinned images regularly.

Native packages are compatible wheels: pydantic-core uses
`cp312-cp312-musllinux_1_1_x86_64`; psycopg-binary and SQLAlchemy use
`cp312-cp312-musllinux_1_2_x86_64`. Other installed distributions have pure-Python
wheel tags. No glibc native wheels were reused. Runtime pip absence was verified.

## Verification

| Check | Actual result |
| --- | --- |
| Production build | Passed; linux/amd64 |
| Unit tests inside production image | 16 passed |
| PostgreSQL 16 integration tests | 2 passed |
| Ruff | Passed |
| Health, readiness, version, metrics | Passed status and content checks |
| Database unavailable at startup | Ready 503; health 200 |
| Real database outage/recovery | Ready 200 → 503 → 200; app not restarted; health 200 during outage |
| Graceful SIGTERM shutdown | Exit 0, shutdown-complete log, no OOM |
| Runtime identity | UID/GID 10001; observed UID 10001 |
| HTTPS to pypi.org | HTTP 200; CERT_REQUIRED and hostname verification enabled; 118 trusted CAs |
| Trivy OS and Python scan | Exit 0; zero CRITICAL/HIGH/MEDIUM/LOW/UNKNOWN findings |
| Inventory versus Task 20 | Identical: 38 OS and 19 Python distributions |
| Size | 166,187,894 bytes (~166.19 MB), versus Task 20 166,188,040 bytes |

The 146-byte size difference is consistent with changed build metadata; the detected
package inventory is unchanged. No vulnerability-count differences were found. Trivy used the
same digest and same-day database as Task 20, with all severities, unfixed findings
retained and no suppressions. Non-fatal Starlette/httpx deprecation warning remains.
PostgreSQL test containers were stopped and volumes preserved. HTTPS testing does
not establish RDS TLS compatibility; the database test used local PostgreSQL.

Image index: `sha256:978db5dde97e810d736347d406298c920d8020d23e001a729c943015710b7631`

AMD64 platform manifest:
`sha256:b6321bf889d7598f9077eea4b300202d95dadd7713f5d20395ff5b781bf04ffa`

Local tag: `rdp-review:task21-alpine`. This is deliberately not an immutable release
tag. BuildKit provenance records the base material, platform and Git HEAD
`84affd60fb97df0019a09d9c162acaef9f824a47`, but source changes are uncommitted.
That Git revision alone does **not** identify this build's source. Source hashes
and the explicit dirty-state marker are recorded in
[review.json](../evidence/task21/review.json). Provenance is not independently signed.
Full scan and build metadata are preserved alongside that file.

## Release review and limits

Tracked and non-ignored untracked files were scanned with Trivy's secret scanner;
no secret findings were reported. This covers the proposed commit surface, not
ignored `.secrets`, `.env`, state, local tools or Git history. No secret values
were printed. File hashes verified that app source, tests, Terraform inputs,
Compose, pyproject and dockerignore were preserved; only the Dockerfile changed
among those inputs. Prior Task 19/20 evidence remains intact.

Remaining risks:

- Zero known findings is not proof that bundled/static native libraries are fully
  covered. Retain the Task 20 zlib patch analysis and scanner limitations.
- Musl DNS, locales, threading and performance differ from glibc. Long-running
  pool/load tests, production networking and RDS TLS have not been exercised.
- Python dependency ranges and apk repositories are still moving build inputs.
  The base is digest-pinned, but **bit-for-bit reproducibility is not established**.
  The supplied commands produce a clean Git-derived, auditable release; dependency
  and artifact hash locking is still required if strict reproducibility is a gate.
- A clean approved commit and rebuilt/rescanned image are required before publishing.
  Never assign the old `git-84affd60fb97` tag to these changes. Deployment still
  needs separate authorization. No risk acceptance was created automatically.

## Exact next commands — not executed

Review all paths before staging. These explicit paths cover the currently pending
Task 19–21 changes; no Terraform, secrets, local tools or state are staged:

```powershell
git diff -- app/Dockerfile
git status --short
git add -- app/Dockerfile docs/container-vulnerability-remediation.md docs/runtime-base-evaluation.md docs/runtime-candidates docs/alpine-production-release-review.md evidence/task19-remediation.json evidence/task20 evidence/task21
git diff --cached --check
git diff --cached --stat
# Inspect staged contents, then commit only after approving that review:
git commit -m "Promote tested Python 3.12 Alpine runtime and preserve security evidence"
```

Build from the resulting clean commit. Stop on every error:

```powershell
if (git status --porcelain) { throw 'Working tree is not clean' }
$sha = (git rev-parse HEAD).Trim()
$tag = 'git-' + $sha.Substring(0, 12)
if ($tag -eq 'git-84affd60fb97') { throw 'Old immutable tag must not be reused' }
$localImage = 'rdp-release:' + $tag
New-Item -ItemType Directory -Force .tools/release | Out-Null
$env:BUILDX_GIT_CHECK_DIRTY = '1'
docker buildx build --load --platform linux/amd64 --provenance=mode=min --metadata-file .tools/release/build-metadata.json --label "org.opencontainers.image.revision=$sha" -f app/Dockerfile -t $localImage .
if ($LASTEXITCODE -ne 0) { throw 'Build failed' }
docker image inspect $localImage --format '{{.Os}}/{{.Architecture}} {{.Config.User}}'
docker save -o .tools/release/image.tar $localImage
if ($LASTEXITCODE -ne 0) { throw 'Image export failed' }
docker run --rm -v "${PWD}/.tools:/work" aquasec/trivy@sha256:8f6bb947dbc528902e11f2f5be52f7b519f6a39d5d148f41166f2040499768fb image --input /work/release/image.tar --cache-dir /work/trivy-cache --scanners vuln --list-all-pkgs --format json --output /work/release/scan.json --exit-code 1
if ($LASTEXITCODE -ne 0) { throw 'Release scan failed; investigate findings' }
```

Re-run the 18 tests and runtime/TLS/recovery checks against **this release image**
before pushing; prior review-image results do not substitute for a changed build.
Pass `APP_VERSION=$tag` and `GIT_SHA=$sha` at runtime; the Dockerfile intentionally
does not bake either value. Preserve release metadata outside tracked files so
verification does not dirty the release source tree.

Only after release verification and explicit publishing approval:

```powershell
# Existing configured ECR credential helper handles authentication; no password output.
. .\.tools\enable-ecr-auth.ps1
$env:AWS_PROFILE = 'rdp-dev'
$env:AWS_REGION = 'ap-southeast-2'
$repositoryUrl = (terraform -chdir=infra/envs/ecr output -raw repository_url).Trim()
if ($LASTEXITCODE -ne 0 -or -not $repositoryUrl) { throw 'Repository lookup failed' }
docker tag $localImage "${repositoryUrl}:$tag"
if ($LASTEXITCODE -ne 0) { throw 'Tag failed' }
docker push "${repositoryUrl}:$tag"
if ($LASTEXITCODE -ne 0) { throw 'Push failed' }
```

The helper is existing ignored local configuration, not a portable repository
dependency. If unavailable, repair authentication before attempting a push; do
not store credentials in tracked files. Keep registry/account identifiers private.
After an approved push, verify the remote index and AMD64 child digest against the
local artifact and scan that child in ECR. Do not scan the OCI index itself.
