# AEGIS Engineer Desktop

Flutter desktop workstation for AEGIS security engineers performing authorized defensive security operations across customer tenants.

## Targets
Windows, Linux and macOS. Generate native runner projects with the installed Flutter SDK:

```bash
cd apps/engineer-desktop
flutter create --platforms=windows,linux,macos .
flutter pub get
flutter analyze
flutter test
```

## Architecture
Feature-first Flutter modules, Riverpod state/dependency injection, GoRouter navigation, Dio API transport and an abstract realtime gateway. Backend services remain authoritative for authentication, tenant membership, permissions, approvals and audit.

## Security boundaries
- No customer infrastructure credentials or direct privileged access are stored in this client.
- Tenant scope is derived and validated by the authenticated backend.
- Production actions remain unavailable until server authorization, durable audit, scoped approvals and verification exist.
- Never fabricate alerts, incidents, telemetry, customer records or AI activity.
- Never commit secrets.

This is a structural scaffold, not a connected production SOC client.
