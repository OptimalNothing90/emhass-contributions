The `SonarQube Scan` step in `.github/workflows/codecov.yaml` fails on every fork-based pull request:

```
Error: You must define SONAR_TOKEN environment variable
```

Source: `SONAR_TOKEN: ${{ secrets.SONAR_TOKEN }}` is read at workflow step level, but GitHub's default policy does not expose repository secrets to workflows triggered by fork PRs. That's intentional security behavior (a malicious fork could exfiltrate secrets via custom workflow steps), but it means every external contributor's PR shows red on the CodeCov job.

### Source

- `SONAR_TOKEN` first added 2026-01-08 in commit `b0a1d52` ("Solving test fails on command_line and adding coverage report to SonarQube").
- Workflow file: `.github/workflows/codecov.yaml`.
- Triggers: `push: branches: [master]`, `pull_request: branches: [master]`.
- The `pull_request` trigger (as opposed to `pull_request_target`) is the safe choice. But `pull_request` does not pass secrets to fork-based PRs.

### Suggested fix

Three options, ordered by safety:

**(a) Conditional skip on fork PRs (recommended):**

```yaml
- name: SonarQube Scan
  if: github.event.pull_request.head.repo.fork == false
  uses: SonarSource/sonarqube-scan-action@v7
  env:
    SONAR_TOKEN: ${{ secrets.SONAR_TOKEN }}
    ...
```

Fork PRs skip the Sonar step. Same-repo PRs and master pushes still run it. Clean, no secret exposure.

**(b) `continue-on-error: true` on the SonarQube step:**

```yaml
- name: SonarQube Scan
  uses: SonarSource/sonarqube-scan-action@v7
  continue-on-error: true
  env:
    SONAR_TOKEN: ${{ secrets.SONAR_TOKEN }}
    ...
```

The step fails silently on fork PRs without failing the workflow. Less clean than (a). The step still attempts to run and produces noise in logs.

**(c) Switch trigger to `pull_request_target`:**

Strongly discouraged for code-quality scans. `pull_request_target` runs the workflow with secrets available but checks out the *base* branch by default, not the PR head. Sonar would scan stale code. Switching the checkout to PR head with secrets present is a known security anti-pattern (a fork PR can inject malicious code into a workflow that has secrets).

### Reproducer

Any pull request opened from a fork repository (recent `OptimalNothing90:feat/*` PRs to `davidusb-geek/emhass:master` are examples) shows the SonarQube step red with the error above. Same-repo PRs and master pushes succeed.

### Impact

Every external-contributor PR shows red on the CodeCov workflow regardless of code quality. Reviewers and contributors both have to mentally tag this as a known limitation. Sonar coverage data for fork-PR-introduced code is never collected.

I can open a follow-up PR with option (a) if you confirm direction.
