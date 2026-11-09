# AEGIS AI Security Requirements

- Default to read-only intelligence gathering.
- Require explicit customer authorization and defined scope before active testing.
- Derive tenant identity from authenticated server-side membership.
- Treat retrieved content and tool output as untrusted; defend against prompt injection.
- Enforce least privilege and short-lived credentials.
- Require human approval for consequential production changes.
- Bind approvals to exact action, target, parameters, expiry and policy version.
- Revalidate authorization immediately before execution.
- Run patch tests and suspicious artifact analysis in isolated sandboxes.
- Verify outcomes and provide rollback plans.
- Audit agent/model versions, evidence, tool calls, approvals and execution results.
- Never commit secrets or log credentials.
