# Hosted CI platform checksum correction

Task 32 published the reviewed `main` branch to
`https://github.com/priyanka13-gb/RDP-Aws`. No force push, visibility change,
AWS deployment, image publication or credential modification was performed.

The [first hosted run](https://github.com/priyanka13-gb/RDP-Aws/actions/runs/43485986344)
for `af36b10187ef2bb42ddf78e9558f855a5adaecfc` failed only in the Terraform job.
Hosted Ruff/unit tests (93), PostgreSQL16 integration tests (2), the AMD64 Docker
build and Trivy gate passed. The hosted scan reported zero findings across
38 OS and 19 Python packages. Its sanitized artifacts are retained for seven days.

## Root cause and minimal correction

A credential-free Linux reproduction showed that `init -lockfile=readonly`
succeeded, warning that the lock file was not updated. `validate` then rejected
the cached AWS provider package because its checksum was absent from the lock
file. The root and network-module lock files included the Windows h1 checksum and signed
archive checksums, but lacked the Linux h1 checksum required by this execution
path. Windows-only validation had not exposed this problem.

Terraform 1.17.1 `providers lock -platform=linux_amd64` was run in an isolated
Linux copy. It retrieved AWS provider 6.71.0, signed by HashiCorp. Only the new
verified Linux h1 checksum was added to the bootstrap, dev, ECR and network-module lock files.
The selected version, constraints and every existing checksum were preserved.
No Terraform resource configuration, backend metadata or state was changed.
CI still uses readonly lock files and rejects checksum mismatches; no checksum
verification or security gate was bypassed.

HashiCorp documents pre-populating target-platform checksums with
[`terraform providers lock`](https://developer.hashicorp.com/terraform/cli/commands/providers/lock).
For future provider upgrades, review signed packages for both platforms in an
isolated copy before changing the committed locks:

```text
terraform providers lock -platform=windows_amd64 -platform=linux_amd64
```

Do not use `init -upgrade`, remove checksum enforcement, modify remote state or
regenerate locks blindly to resolve a platform-specific validation failure.

## Hosted verification procedure

The correction is revalidated locally before committing and pushed only to
the same `origin/main` branch. Verify a completed successful CI run for that exact
commit, with all four jobs successful and the sanitized artifacts downloaded:
unit, PostgreSQL, Terraform and vulnerability summaries. A queued, skipped or
in-progress run is not a successful verification.

Task 32 records the final run ID, URL, commit, job conclusions and downloaded
sanitized summaries in ignored `.tools/task32/` to avoid triggering another CI
run solely to commit its own result. No raw hosted logs, credential-manager
output, access tokens or account identifiers belong in published evidence.

CI has contents:read only, no OIDC permission, no AWS secrets, no apply/destroy,
and no registry push. The separate release workflow remains manual-only, false
by default and is not dispatched by a push. This check does not prove a live
OIDC release or ECS rollback, and does not authorize the next AWS deployment.
