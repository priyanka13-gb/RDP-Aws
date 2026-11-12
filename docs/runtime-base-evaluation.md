# Secure runtime base evaluation

Evaluation date: 2026-11-06. Recommendation: adopt the evaluated **official Python
3.12 Alpine candidate** in a separately reviewed change. It is the best supported,
compatible option tested here, not a guarantee of vulnerability-free execution.
The application Dockerfile has not been replaced. No image was pushed and no AWS,
Terraform, credentials or Git commit was changed.

## Actual comparison

All counts include unfixed findings and all severities. Counts are package/CVE
entries, not unique CVEs. Sizes are Docker's local image Size in decimal MB, not
compressed ECR transfer sizes. Package counts come from Trivy's complete inventory.

| Candidate | Python / libc | CRITICAL | HIGH | MEDIUM | LOW | Fixable entries | Size MB | OS / Python packages | Scan exit |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: |
| Latest 3.12 slim | 3.12.16 / glibc | 0 | 49 | 75 | 62 | 0 | 319.34 | 87 / 19 | 1 |
| 3.12 Alpine 3.24.4 | 3.12.16 / musl | 0 | 0 | 0 | 0 | 0 | 166.19 | 38 / 19 | 0 |
| Distroless Debian 13 | 3.13.5 / glibc | 0 | 35 | 114 | 54 | 0 | 181.20 | 38 / 19 | 1 |

All three builds succeeded for Linux AMD64. All run as UID/GID `10001:10001`,
confirmed both through image configuration and actual `os.getuid()`. All have
zero Python-distribution findings. Distroless Python interpreter advisories are
reported as **OS packages**, so zero Python-distribution findings does not mean
its Python interpreter has no findings.

The latest slim tag resolved to the same digest as Task 19. Its scan is unchanged.
Alpine is justified by the maintained publisher, retained Python minor version,
native musllinux dependency availability, patched zlib package, successful tests,
and reduced package inventory together. Distroless's lack of a shell does not
outweigh its residual findings and Python minor-version migration in this case.

## Publisher, support and ABI

- Slim and Alpine are [Docker Official Python images](https://hub.docker.com/_/python),
  maintained through docker-library/python. Python 3.12 is in security support
  through October 2028; 3.13 through October 2029 according to the
  [Python support table](https://devguide.python.org/versions/).
- Alpine 3.24 main is supported through 2028-06-01 according to the
  [Alpine release policy](https://alpinelinux.org/releases/). Community packages
  have a shorter support window. The Python interpreter comes from the official
  Python image, not Alpine's python3 package. Continue updating both image and OS.
- Distroless comes from Google's `gcr.io/distroless` namespace and the
  [GoogleContainerTools project](https://github.com/GoogleContainerTools/distroless).
  Its [Python documentation](https://github.com/GoogleContainerTools/distroless/blob/main/python3/README.md)
  requires a compatible builder: we used Python 3.13 slim Trixie for the Debian 13
  Python 3.13 runtime. Its [support policy](https://github.com/GoogleContainerTools/distroless/blob/main/SUPPORT_POLICY.md)
  estimates Python Debian 13 support until three months after Debian 14 release.
- AMD64 pull, build and runtime succeeded for every candidate. Publisher namespace
  and registry digest were verified; independent cryptographic signature/attestation
  validation was **not** performed. Do not equate a digest pin with publisher trust.
- Slim uses `cpython-312-x86_64-linux-gnu`, Alpine
  `cpython-312-x86_64-linux-musl`, distroless `cpython-313-x86_64-linux-gnu`.
  Dependencies were installed in each matching builder; no CPython 3.12/glibc
  native wheels were copied into musl or Python 3.13. Psycopg-binary and
  pydantic-core imports and functional behavior passed. Distroless uses an explicit
  `/usr/bin/python3` entrypoint and a `python` alias for existing health checks.

Digest-pinned build recipes are under [runtime-candidates](runtime-candidates/).
They are evaluation artifacts; use the repository root as their Docker context:

```powershell
docker build --platform linux/amd64 -f docs/runtime-candidates/alpine.Dockerfile -t rdp-eval:task20-alpine .
```

The exact pulled digests, image IDs, installed Python package versions, ABI,
source hashes and report hashes are recorded in
[comparison.json](../evidence/task20/comparison.json). Base digests are fixed;
unlocked Python dependency ranges and apt/apk repositories remain moving inputs.
Lock and hash Python dependencies before claiming bit-for-bit reproducibility.

## Original ECR HIGH findings

The historical ECR scan covered AMD64 child
`sha256:506f81572a2a39f1d3f33c21e3cafc836ec8918ef28228d2f8835c5e1d20929d`:
4 HIGH, 9 MEDIUM, 3 LOW. Task 19 evidence is preserved unchanged; this evaluation
did not run a new ECR scan. These four are OS source-package findings.

| CVE / Debian advisory | ECR package and installed version | Debian fix status | Candidate result |
| --- | --- | --- | --- |
| [CVE-2026-19499](https://security-tracker.debian.org/tracker/CVE-2026-19499) | glibc 2.41-12+deb13u4 | Trixie vulnerable; unstable fixed at 2.43-5 | Retained in slim/distroless; glibc absent from Alpine OS inventory |
| [CVE-2026-5435](https://security-tracker.debian.org/tracker/CVE-2026-5435) | glibc 2.41-12+deb13u4 | Trixie vulnerable; unstable fixed at 2.43-3 | Retained in slim/distroless; Alpine uses musl |
| [CVE-2026-76844](https://security-tracker.debian.org/tracker/CVE-2026-76844) | zlib 1.3.dfsg+really1.3.1-1 | Trixie vulnerable; unstable fixed at 1:1.3.dfsg+really1.3.2-4 | Retained in slim/distroless; not reported in Alpine; patch relationship discussed below |
| [CVE-2026-85091](https://security-tracker.debian.org/tracker/CVE-2026-85091) | zlib 1.3.dfsg+really1.3.1-1 | Trixie vulnerable; unstable fixed at 1:1.3.dfsg+really1.3.2-4 | Retained in slim/distroless; Alpine 1.3.2-r1 includes vendor patch |

The Debian binary zlib version is `1:1.3.dfsg+really1.3.1-1+b1`. Debian rates the
glibc issues lower than ECR; Trivy rates them MEDIUM. This is vendor severity
variation, not a fix. Neither application source nor its routes calls strfmon or
the deprecated resolver formatting functions directly. Indirect reachability
through native libraries was not exhaustively established.

Alpine's [zlib APKBUILD](https://raw.githubusercontent.com/alpinelinux/aports/3.24-stable/main/zlib/APKBUILD)
explicitly marks CVE-2026-85091 fixed at 1.3.2-r1 and includes
[the upstream patch](https://raw.githubusercontent.com/alpinelinux/aports/3.24-stable/main/zlib/CVE-2026-85091.patch).
The installed package is exactly 1.3.2-r1. The patch resets the stale input pointer
after failed writes. Debian's tracking for CVE-2026-76844 associates it with the
same fix; therefore coverage of that CVE by this patch is a reasoned inference,
not an independently reproduced exploit test. Alpine's APKBUILD does not explicitly
name 76844. Preserve this distinction in security acceptance.

## Triage of all original 49 Trivy HIGH entries

The [complete original entry list](runtime-candidates/original-high-findings.md)
records package, version and fix for each row. They represent **13 unique CVEs**.
All 49 have no fixed version reported for this Debian branch. Upstream or unstable
fixes must not be installed blindly into a stable image.

| CVEs | Binary package entries | Reachability assessment and uncertainty |
| --- | ---: | --- |
| CVE-2026-76642, 78408, 78409, 78410 | 36 (9 util-linux binaries per CVE) | Concern privileged mounts, mount hooks or nsenter. Application does not invoke these tools; runs non-root. Source-package mapping to libraries such as libuuid may overstate individual binary applicability. Not proven false positives; retain all rows. |
| CVE-2026-54369 | 1 (libacl1) | ACL/symlink privilege operations are not in application routes. Native-library reachability not formally proved absent. |
| CVE-2025-69720 | 4 (ncurses/tinfo) | No interactive terminal or curses use in service. Shared-library presence alone does not prove exploitable route; retain findings. |
| CVE-2026-119373, 119374, 119379 | 3 (SQLite) | Application explicitly uses PostgreSQL and no SQLite path. SQLite FTS/session operations not exercised; future code could change exposure. |
| CVE-2026-16742 | 2 (libsystemd0/libudev1) | Advisory concerns systemd-homed; service does not run systemd. Candidate false applicability from source-package attribution; not suppressed without binary-level verification. |
| CVE-2026-9538 | 1 (perl-base) | No Perl/tar processing in app. Check affected Perl module presence before declaring false positive. |
| CVE-2026-76844, 85091 | 2 (zlib1g) | Shared library can be loaded indirectly; vulnerable gz-write/error paths not used directly by app. No exploit or exhaustive native call-graph proof performed. |

The scanner title for 76844 refers to webpack path traversal even though its package
and Debian advisory identify zlib. This is a metadata inconsistency requiring
vendor clarification, **not** grounds to discard the finding. The upstream range
text for 85091 also differs from Debian's affected backport classification; use
distribution tracking and retain it. No confirmed false positives were suppressed.
No HIGH was demonstrated remotely exploitable through the four current endpoints;
absence of a demonstrated path is not proof of non-reachability.

## Validation performed

For **each of the three candidates**, independently:

- 16 unit tests passed inside its own Python runtime. Test tools were mounted
  separately and are not included in the candidate images.
- Both existing integration tests passed against actual PostgreSQL 16, including
  database name/version query and pooled SQLAlchemy/psycopg connectivity.
- `/health`, `/ready`, `/version`, `/metrics` returned 200 with database disabled;
  version body and metrics content verified. Containers used network isolation,
  0.25 CPU and 512 MiB during these checks.
- With a configured unreachable PostgreSQL address: `/ready` returned 503 while
  `/health`, `/version`, `/metrics` remained 200.
- Startup passed; SIGTERM shutdown completed within 15 seconds with exit 0,
  application-shutdown log confirmation and no OOM.
- Existing Compose health checks passed without editing Compose. Test containers
  were stopped; database volumes were preserved. No AWS secret was used or changed.

Host checks additionally passed: 16 unit tests, 2 opt-in integration skips, Ruff.
Host Python is 3.15.2; the in-container tests remove that host-version ambiguity.
Starlette emitted a non-fatal httpx deprecation warning; no test failure was hidden.
All candidate builds and tests passed. An initial unprivileged Docker inventory
call was denied by the local pipe permissions; subsequent authorized execution
succeeded. This was a tooling access failure, not an image failure.

## Scanner method and evidence

Trivy image was pinned to
`aquasec/trivy@sha256:8f6bb947dbc528902e11f2f5be52f7b519f6a39d5d148f41166f2040499768fb`.
All three scans used the same database updated **2026-11-06 06:50:38 UTC**,
downloaded that day. `--skip-db-update` froze that dataset for comparison; it did
not skip vulnerability scanning. Full image archives were scanned with
`--scanners vuln --list-all-pkgs --format json --exit-code 1`. No severity filter,
ignore-unfixed switch or CVE allowlist was used. Full reports, inventories, build
logs and runtime/test logs are preserved in [evidence/task20](../evidence/task20/).
Original Task 19 evidence is unchanged.

The scans correctly fail for slim/distroless (exit 1) and pass for Alpine (exit 0).
Distroless retains the four original CVEs and adds findings in Expat and Debian's
Python interpreter packages. Every remaining HIGH/CRITICAL row is recorded in
[candidate-high-findings.md](runtime-candidates/candidate-high-findings.md), with
installed versions and reported fix status. No CRITICAL was reported in any final
candidate, and no remaining finding had a branch-specific fixed version in this
dataset. That does not establish the absence of upstream patches.

## Residual risks and next decision

1. Approve Alpine as the next implementation candidate, then replace the production
   Dockerfile only in a separately reviewed change. No automatic promotion occurred.
2. Musl differs from glibc in DNS, threading and locale behavior. Current endpoints,
   native extensions and PostgreSQL passed; production TLS, load, long-running pool
   behavior and AWS networking were not tested. The PostgreSQL test uses the existing
   local setup, not TLS/RDS.
3. Trivy inventories distro packages and Python metadata; it does not prove complete
   coverage of copied/static native code bundled inside psycopg-binary or upstream
   CPython. Keep those packages patched and review their upstream advisories. Zero
   known findings is not zero risk. Alpine retains a shell/package manager, unlike
   distroless; non-root limits but does not eliminate post-compromise capability.
4. Verify image signatures/provenance, lock dependency inputs and retain SBOM/scan
   evidence before release. Rebuild from an approved clean commit with a new
   immutable tag; these local evaluation images include uncommitted changes.
5. Rescan with current data at release time. After separately approved image push,
   verify the ECR AMD64 child digest and its scan. Local scan success is not ECR
   validation. No ECS/ALB deployment is authorized by this evaluation.
6. If retaining slim or distroless, obtain explicit time-limited risk acceptance
   with an owner for the unresolved HIGHs, or wait for vendor fixes. Counts alone
   do not justify acceptance, and no risk exception was created here.
