import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../app/theme/aegis_theme.dart';

class SocShell extends StatelessWidget {
  const SocShell({
    required this.location,
    required this.child,
    super.key,
  });

  final String location;
  final Widget child;

  static const items = <({String label, String path, IconData icon})>[
    (label: 'Overview', path: '/', icon: Icons.grid_view_rounded),
    (label: 'Companies', path: '/companies', icon: Icons.business_outlined),
    (
      label: 'Live Monitoring',
      path: '/monitoring',
      icon: Icons.monitor_heart_outlined
    ),
    (
      label: 'Threat Alerts',
      path: '/alerts',
      icon: Icons.notifications_active_outlined
    ),
    (
      label: 'Investigations',
      path: '/investigations',
      icon: Icons.manage_search
    ),
    (label: 'AI Agents', path: '/ai-agents', icon: Icons.smart_toy_outlined),
    (
      label: 'Vulnerabilities',
      path: '/vulnerabilities',
      icon: Icons.bug_report_outlined
    ),
    (label: 'Patch Center', path: '/patch-center', icon: Icons.code_rounded),
    (label: 'Incidents', path: '/incidents', icon: Icons.assignment_outlined),
    (label: 'Reports', path: '/reports', icon: Icons.analytics_outlined),
    (label: 'Team & Shifts', path: '/team', icon: Icons.groups_outlined),
    (label: 'Settings', path: '/settings', icon: Icons.settings_outlined),
  ];

  @override
  Widget build(BuildContext context) {
    final selected = items.indexWhere((item) => item.path == location);
    return LayoutBuilder(
      builder: (context, constraints) {
        final compact = constraints.maxWidth < 1180;
        final sidebarWidth = compact ? 76.0 : 248.0;
        return Scaffold(
          body: Row(
            children: [
              SizedBox(
                width: sidebarWidth,
                child: _Sidebar(
                  selected: selected < 0 ? 0 : selected,
                  compact: compact,
                ),
              ),
              Expanded(
                child: Column(
                  children: [
                    const _TopBar(),
                    Expanded(child: child),
                  ],
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}

class _Sidebar extends StatelessWidget {
  const _Sidebar({required this.selected, required this.compact});

  final int selected;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    return ColoredBox(
      color: AegisTheme.surface,
      child: Column(
        children: [
          Padding(
            padding:
                EdgeInsets.fromLTRB(compact ? 0 : 22, 22, compact ? 0 : 16, 22),
            child: Row(
              mainAxisAlignment:
                  compact ? MainAxisAlignment.center : MainAxisAlignment.start,
              children: [
                const Icon(Icons.shield_rounded,
                    color: AegisTheme.accent, size: 29),
                if (!compact) ...[
                  const SizedBox(width: 11),
                  const Text(
                    'AEGIS',
                    style: TextStyle(
                      color: AegisTheme.textPrimary,
                      fontSize: 20,
                      fontWeight: FontWeight.w800,
                      letterSpacing: 2,
                    ),
                  ),
                ],
              ],
            ),
          ),
          const Divider(height: 1),
          Expanded(
            child: ListView.builder(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 12),
              itemCount: SocShell.items.length,
              itemBuilder: (context, index) {
                final item = SocShell.items[index];
                final active = index == selected;
                return Padding(
                  padding: const EdgeInsets.only(bottom: 4),
                  child: Tooltip(
                    message: compact ? item.label : '',
                    child: Material(
                      color:
                          active ? AegisTheme.accentSoft : Colors.transparent,
                      borderRadius: BorderRadius.circular(9),
                      child: InkWell(
                        borderRadius: BorderRadius.circular(9),
                        onTap: () => context.go(item.path),
                        child: Container(
                          height: 43,
                          padding: EdgeInsets.symmetric(
                              horizontal: compact ? 0 : 12),
                          decoration: BoxDecoration(
                            borderRadius: BorderRadius.circular(9),
                            border: active
                                ? const Border(
                                    left: BorderSide(
                                        color: AegisTheme.accent, width: 2),
                                  )
                                : null,
                          ),
                          child: Row(
                            mainAxisAlignment: compact
                                ? MainAxisAlignment.center
                                : MainAxisAlignment.start,
                            children: [
                              Icon(
                                item.icon,
                                size: 19,
                                color: active
                                    ? AegisTheme.accent
                                    : AegisTheme.textMuted,
                              ),
                              if (!compact) ...[
                                const SizedBox(width: 12),
                                Expanded(
                                  child: Text(
                                    item.label,
                                    maxLines: 1,
                                    overflow: TextOverflow.ellipsis,
                                    style: TextStyle(
                                      color: active
                                          ? AegisTheme.textPrimary
                                          : AegisTheme.textMuted,
                                      fontSize: 12.5,
                                      fontWeight: active
                                          ? FontWeight.w600
                                          : FontWeight.w500,
                                    ),
                                  ),
                                ),
                              ],
                            ],
                          ),
                        ),
                      ),
                    ),
                  ),
                );
              },
            ),
          ),
          Padding(
            padding: EdgeInsets.all(compact ? 12 : 16),
            child: compact
                ? const Tooltip(
                    message: 'Services not connected',
                    child: Icon(Icons.cloud_off_outlined,
                        color: AegisTheme.warning, size: 18),
                  )
                : const Row(
                    children: [
                      Icon(Icons.circle, color: AegisTheme.warning, size: 8),
                      SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          'Services not connected',
                          style: TextStyle(
                              color: AegisTheme.textMuted, fontSize: 11),
                        ),
                      ),
                    ],
                  ),
          ),
        ],
      ),
    );
  }
}

class _TopBar extends StatelessWidget {
  const _TopBar();

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 66,
      padding: const EdgeInsets.symmetric(horizontal: 26),
      decoration: const BoxDecoration(
        border: Border(bottom: BorderSide(color: AegisTheme.border)),
      ),
      child: Row(
        children: [
          const Text(
            'SECURITY OPERATIONS',
            style: TextStyle(
              color: AegisTheme.textMuted,
              fontSize: 10,
              fontWeight: FontWeight.w700,
              letterSpacing: 1.4,
            ),
          ),
          const Spacer(),
          SizedBox(
            width: 230,
            child: TextField(
              decoration: const InputDecoration(
                hintText: 'Search workspace',
                prefixIcon: Icon(Icons.search, size: 18),
                isDense: true,
              ),
            ),
          ),
          const SizedBox(width: 18),
          Container(
            width: 32,
            height: 32,
            decoration: BoxDecoration(
              color: AegisTheme.elevated,
              borderRadius: BorderRadius.circular(9),
              border: Border.all(color: AegisTheme.border),
            ),
            child: const Icon(Icons.account_circle_outlined,
                size: 19, color: AegisTheme.textMuted),
          ),
          const SizedBox(width: 9),
          const Text(
            'Engineer workspace',
            style: TextStyle(color: AegisTheme.textPrimary, fontSize: 12),
          ),
        ],
      ),
    );
  }
}
