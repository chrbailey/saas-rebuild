# Release artifacts

Generated archives are deliberately not committed. This directory is populated
by the release workflow from tagged source with:

```bash
python scripts/package_skills.py --output-dir dist
```

Each GitHub Release contains one versioned ZIP per skill, `SHA256SUMS`, and a
GitHub build-provenance attestation. For local verification without writing
artifacts, run `python scripts/package_skills.py --check`.
