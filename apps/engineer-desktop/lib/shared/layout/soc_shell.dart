import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../app/theme/aegis_theme.dart';

class SocShell extends StatelessWidget {
  const SocShell({required this.location, required this.child, super.key});
  final String location;
  final Widget child;

  static const items = <({String label, String path, IconData icon})>[
    (label: 'Overview', path: '/', icon: Icons.dashboard_outlined),
    (label: 'Companies', path: '/companies', icon: Icons.business_outlined),
    (label: 'Live Monitoring', path: '/monitoring', icon: Icons.monitor_heart_outlined),
    (label: 'Threat Alerts', path: '/alerts', icon: Icons.notifications_active_outlined),
    (label: 'Investigations', path: '/investigations', icon: Icons.manage_search),
    (label: 'AI Agents', path: '/ai-agents', icon: Icons.smart_toy_outlined),
    (label: 'Vulnerabilities', path: '/vulnerabilities', icon: Icons.bug_report_outlined),
    (label: 'Patch Center', path: '/patch-center', icon: Icons.code),
    (label: 'Incidents', path: '/incidents', icon: Icons.assignment_outlined),
    (label: 'Reports', path: '/reports', icon: Icons.analytics_outlined),
    (label: 'Team & Shifts', path: '/team', icon: Icons.groups_outlined),
    (label: 'Settings', path: '/settings', icon: Icons.settings_outlined),
  ];

  @override
  Widget build(BuildContext context) {
    final selected = items.indexWhere((item) => item.path == location);
    return Scaffold(body: Row(children: [
      Container(width: 248, color: AegisTheme.surface, child: Column(children: [
        const Padding(padding: EdgeInsets.fromLTRB(22, 24, 16, 22), child: Row(children: [
          Icon(Icons.shield_outlined, color: AegisTheme.accent, size: 30), SizedBox(width: 12),
          Text('AEGIS', style: TextStyle(color: AegisTheme.textPrimary, fontSize: 20, fontWeight: FontWeight.w800, letterSpacing: 2)),
        ])),
        const Divider(height: 1),
        Expanded(child: ListView(padding: const EdgeInsets.symmetric(vertical: 10), children: [
          for (var i = 0; i < items.length; i++) ListTile(
            selected: i == selected,
            selectedTileColor: AegisTheme.elevated,
            leading: Icon(items[i].icon, size: 20),
            title: Text(items[i].label, style: const TextStyle(fontSize: 13)),
            onTap: () => context.go(items[i].path),
          ),
        ])),
        const Padding(padding: EdgeInsets.all(16), child: Row(children: [
          Icon(Icons.circle, color: Colors.amber, size: 9), SizedBox(width: 8),
          Expanded(child: Text('Services not connected', style: TextStyle(color: AegisTheme.textMuted, fontSize: 11))),
        ])),
      ])),
      Expanded(child: Column(children: [
        Container(height: 64, padding: const EdgeInsets.symmetric(horizontal: 24),
          decoration: const BoxDecoration(border: Border(bottom: BorderSide(color: AegisTheme.border))),
          child: const Row(children: [
            Text('SECURITY OPERATIONS', style: TextStyle(color: AegisTheme.textMuted, fontSize: 11, letterSpacing: 1.2)),
            Spacer(), Icon(Icons.account_circle_outlined, color: AegisTheme.textMuted), SizedBox(width: 8), Text('Engineer workspace'),
          ])),
        Expanded(child: child),
      ])),
    ]));
  }
}
