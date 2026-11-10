# AEGIS Engineer Desktop

Flutter desktop workstation for AEGIS security engineers performing authorized defensive security operations across customer tenants.

## Status

This application is an actively developed client scaffold. It is not yet a production-connected SOC workstation. Feature pages must not fabricate telemetry, alerts, incidents, customer records or AI activity.

## Supported targets

Windows, Linux and macOS. The CI workflow generates the native runner for each target on its matching GitHub-hosted runner and performs a release build. To generate native runner folders locally:

```bash
cd apps/engineer-desktop
flutter create --platforms=windows,linux,macos .
flutter pub get
dart format --output=none --set-exit-if-changed .
flutter analyze --fatal-infos
flutter test
```

Linux development/build prerequisites (Ubuntu/Debian):

```bash
sudo apt-get install clang cmake ninja-build pkg-config libgtk-3-dev libstdc++-12-dev
```

## Configuration

The API endpoint is a compile-time value. Local development defaults to `http://127.0.0.1:8000`.

```bash
flutter run --dart-define=AEGIS_API_BASE_URL=http://127.0.0.1:8000
```

For a packaged build, provide the HTTPS API endpoint at build time:

```bash
flutter build windows --release --dart-define=AEGIS_API_BASE_URL=https://api.example.com
```

Only absolute HTTP(S) URLs without embedded credentials, query parameters or fragments are accepted. Never put API keys, passwords, signing keys or customer infrastructure credentials in `--dart-define`, source control or application assets. Use an authenticated backend session and platform secure storage for session material once the identity integration is implemented.

## Architecture

Feature-first Flutter modules, Riverpod state/dependency injection, GoRouter navigation, Dio API transport and an abstract realtime gateway. Backend services remain authoritative for authentication, tenant membership, permissions, approvals and audit.

## Security boundaries

- No customer infrastructure credentials or direct privileged access are stored in this client.
- Tenant scope is derived and validated by the authenticated backend.
- Production actions remain unavailable until server authorization, durable audit, scoped approvals and verification exist.
- Never fabricate alerts, incidents, telemetry, customer records or AI activity.
- Never commit secrets.

## Validation

The GitHub Actions workflow runs dependency resolution, repository-wide Dart formatting verification, Flutter analysis, unit/widget tests, and release builds for Linux, Windows and macOS. Each native target is generated and built on its corresponding runner.
