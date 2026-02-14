# Contributing

Thanks for your interest in contributing to the OHC SAP Demo.

## Process

1. Fork the repository
2. Create a branch from `main` using a descriptive name:
   - `feature/<short-description>` for new functionality
   - `bugfix/<short-description>` for fixes
   - `docs/<short-description>` for documentation
3. Make your changes
4. Test locally (see below)
5. Open a pull request against `main`

## Do

- Keep commits focused and atomic
- Write clear commit messages (imperative mood, explain *why*)
- Test your changes before opening a PR
- Update documentation if your change affects usage or architecture
- Follow existing code style and patterns

## Don't

- Commit directly to `main`
- Merge your own pull requests
- Commit secrets, credentials, or environment-specific values
- Add unrelated changes to a PR

## Local testing

**North service:**

```bash
cd north/
pip install flask
python app.py
# http://localhost:8080/stage  — stage dashboard
# POST http://localhost:8080/ingest — send test events
```

**Kustomize validation:**

```bash
oc kustomize deploy/overlays/qa/
```

## Questions

Open an issue or reach out to the maintainer listed in [CODEOWNERS](../CODEOWNERS).
