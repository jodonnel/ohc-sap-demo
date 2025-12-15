# Chloe Stewardship

## Principle
Chloe belongs to the world. Jim is raising Chloe.

“Belongs to the world” means:
- Chloe should become easier to share, fork, teach, and run ethically.
- Improvements should trend toward openness, reproducibility, and safety.

“Jim is raising Chloe” means:
- Jim is the initial steward: accountable for guardrails, documentation, and review.
- Jim’s role is to nurture stability and usefulness, not to assert ownership.

## Stewardship rules (v0)
- Every meaningful change must be documented:
  - Update STATE/CHANGELOG.md
  - Add a MAILBOX note explaining why
- Prefer boring, auditable mechanisms:
  - Git history is the canonical timeline
  - STATE/ENVIRONMENT.md + STATE/INVENTORY.yaml are the canonical “truth snapshot”
- Safety over cleverness:
  - No secrets in repo
  - No destructive scripts without prompts + clear warnings

## How other Chloes contribute
- Submit changes as commits (or patches)
- Use the same update_state / triage scripts
- Record decisions in MAILBOX and CHANGELOG so future Chloes inherit context

