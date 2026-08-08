# Security policy

## Report privately

Do not open a public issue for a vulnerability, leaked tenant artifact,
credential, sanctions-screening false-clear path, audit-integrity defect, or a
way to bypass a documented safety gate.

Use GitHub's **Report a vulnerability** flow for this repository. Include:

- affected commit or release;
- exact reproduction and expected/actual behavior;
- impact, especially whether the result can clear, overwrite, exfiltrate, or
  misclassify data;
- the smallest safe fixture that reproduces it;
- any known workaround.

Do not include real customer, employee, counterparty, or credential data.

## Security boundaries

- The SaaS teardown skill operates through the user's authorized model,
  browser, MCP, API, and storage boundary. It does not create a private data
  plane by itself.
- `raw-local-only` governs saved-artifact distribution. It does not mean a
  hosted model or remote connector did not process the content.
- The export-compliance engine defaults to deterministic/offline adjudication.
  Refresh requires network access; a configured hosted model backend sends a
  minimized case payload to that provider.
- Skill and plugin files are executable instructions. Review a version before
  installing it and verify release digests/provenance where available.

## Supported versions

Security fixes target the current release on `main`. Older pre-1.0 releases
may receive a disclosure note but are not guaranteed a backport.
