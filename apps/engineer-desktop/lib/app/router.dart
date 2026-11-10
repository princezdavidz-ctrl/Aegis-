import 'package:go_router/go_router.dart';

import '../features/ai_agents/presentation/ai_agents_page.dart';
import '../features/alerts/presentation/alerts_page.dart';
import '../features/companies/presentation/companies_page.dart';
import '../features/incidents/presentation/incidents_page.dart';
import '../features/investigations/presentation/investigations_page.dart';
import '../features/monitoring/presentation/monitoring_page.dart';
import '../features/overview/presentation/overview_page.dart';
import '../features/patch_center/presentation/patch_center_page.dart';
import '../features/reports/presentation/reports_page.dart';
import '../features/settings/presentation/settings_page.dart';
import '../features/team/presentation/team_page.dart';
import '../features/vulnerabilities/presentation/vulnerabilities_page.dart';
import '../shared/layout/soc_shell.dart';

final aegisRouter = GoRouter(initialLocation: '/', routes: [
  ShellRoute(
      builder: (context, state, child) =>
          SocShell(location: state.uri.path, child: child),
      routes: [
        GoRoute(path: '/', builder: (_, __) => const OverviewPage()),
        GoRoute(path: '/companies', builder: (_, __) => const CompaniesPage()),
        GoRoute(
            path: '/monitoring', builder: (_, __) => const MonitoringPage()),
        GoRoute(path: '/alerts', builder: (_, __) => const AlertsPage()),
        GoRoute(
            path: '/investigations',
            builder: (_, __) => const InvestigationsPage()),
        GoRoute(path: '/ai-agents', builder: (_, __) => const AiAgentsPage()),
        GoRoute(
            path: '/vulnerabilities',
            builder: (_, __) => const VulnerabilitiesPage()),
        GoRoute(
            path: '/patch-center', builder: (_, __) => const PatchCenterPage()),
        GoRoute(path: '/incidents', builder: (_, __) => const IncidentsPage()),
        GoRoute(path: '/reports', builder: (_, __) => const ReportsPage()),
        GoRoute(path: '/team', builder: (_, __) => const TeamPage()),
        GoRoute(path: '/settings', builder: (_, __) => const SettingsPage()),
      ]),
]);
