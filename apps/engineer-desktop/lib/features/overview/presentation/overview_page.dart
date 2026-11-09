import 'package:flutter/material.dart';

import '../../../app/theme/aegis_theme.dart';

class OverviewPage extends StatelessWidget {
  const OverviewPage({super.key});

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final wide = constraints.maxWidth >= 1120;
        final medium = constraints.maxWidth >= 760;
        final metricWidth = (constraints.maxWidth - 64 - (wide ? 36 : medium ? 24 : 12)) /
            (wide ? 4 : medium ? 2 : 1);
        return SingleChildScrollView(
          padding: EdgeInsets.all(wide ? 30 : 20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('Operations overview', style: TextStyle(
                          color: AegisTheme.textPrimary,
                          fontSize: 25,
                          fontWeight: FontWeight.w700,
                          letterSpacing: -0.5,
                        )),
                        SizedBox(height: 6),
                        Text(
                          'A live view of authorized customer environments and SOC workload.',
                          style: TextStyle(color: AegisTheme.textMuted, fontSize: 12.5),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(width: 12),
                  _ConnectionBadge(),
                ],
              ),
              const SizedBox(height: 24),
              Wrap(
                spacing: 12,
                runSpacing: 12,
                children: [
                  SizedBox(width: metricWidth, child: const _MetricCard(
                    label: 'OPEN ALERTS',
                    value: '—',
                    caption: 'Awaiting telemetry connection',
                    icon: Icons.notifications_active_outlined,
                    tone: AegisTheme.warning,
                  )),
                  SizedBox(width: metricWidth, child: const _MetricCard(
                    label: 'CRITICAL FINDINGS',
                    value: '—',
                    caption: 'No verified findings loaded',
                    icon: Icons.warning_amber_rounded,
                    tone: AegisTheme.danger,
                  )),
                  SizedBox(width: metricWidth, child: const _MetricCard(
                    label: 'PROTECTED ASSETS',
                    value: '—',
                    caption: 'Inventory not connected',
                    icon: Icons.devices_other_outlined,
                    tone: AegisTheme.accent,
                  )),
                  SizedBox(width: metricWidth, child: const _MetricCard(
                    label: 'INTEGRATIONS',
                    value: '0',
                    caption: 'No integrations authorized',
                    icon: Icons.hub_outlined,
                    tone: AegisTheme.success,
                  )),
                ],
              ),
              const SizedBox(height: 18),
              if (wide)
                const Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(flex: 7, child: _ThreatLandscapePanel()),
                    SizedBox(width: 16),
                    Expanded(flex: 5, child: _PriorityQueuePanel()),
                  ],
                )
              else ...[
                const _ThreatLandscapePanel(),
                const SizedBox(height: 16),
                const _PriorityQueuePanel(),
              ],
              const SizedBox(height: 16),
              const _IntegrationPanel(),
              const SizedBox(height: 16),
              const _ActivityPanel(),
              const SizedBox(height: 24),
              const Center(
                child: Text(
                  'AEGIS • Evidence-led security operations',
                  style: TextStyle(color: AegisTheme.textMuted, fontSize: 10),
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}

class _ConnectionBadge extends StatelessWidget {
  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 11, vertical: 8),
    decoration: BoxDecoration(
      color: AegisTheme.elevated,
      borderRadius: BorderRadius.circular(20),
      border: Border.all(color: AegisTheme.border),
    ),
    child: const Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(Icons.circle, color: AegisTheme.warning, size: 7),
        SizedBox(width: 7),
        Text('NOT CONNECTED', style: TextStyle(
          color: AegisTheme.textMuted, fontSize: 9, fontWeight: FontWeight.w700, letterSpacing: 0.7,
        )),
      ],
    ),
  );
}

class _MetricCard extends StatelessWidget {
  const _MetricCard({
    required this.label,
    required this.value,
    required this.caption,
    required this.icon,
    required this.tone,
  });

  final String label;
  final String value;
  final String caption;
  final IconData icon;
  final Color tone;

  @override
  Widget build(BuildContext context) => Container(
    height: 126,
    padding: const EdgeInsets.all(16),
    decoration: BoxDecoration(
      color: AegisTheme.surface,
      borderRadius: BorderRadius.circular(12),
      border: Border.all(color: AegisTheme.border),
    ),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(children: [
          Expanded(child: Text(label, style: const TextStyle(
            color: AegisTheme.textMuted, fontSize: 9, fontWeight: FontWeight.w700, letterSpacing: 0.9,
          ))),
          Icon(icon, color: tone, size: 18),
        ]),
        const Spacer(),
        Text(value, style: const TextStyle(
          color: AegisTheme.textPrimary, fontSize: 27, fontWeight: FontWeight.w700,
        )),
        const SizedBox(height: 3),
        Text(caption, maxLines: 1, overflow: TextOverflow.ellipsis,
          style: const TextStyle(color: AegisTheme.textMuted, fontSize: 10)),
      ],
    ),
  );
}

class _Panel extends StatelessWidget {
  const _Panel({required this.title, required this.subtitle, required this.child});
  final String title;
  final String subtitle;
  final Widget child;

  @override
  Widget build(BuildContext context) => Container(
    width: double.infinity,
    padding: const EdgeInsets.all(18),
    decoration: BoxDecoration(
      color: AegisTheme.surface,
      borderRadius: BorderRadius.circular(12),
      border: Border.all(color: AegisTheme.border),
    ),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(title, style: const TextStyle(color: AegisTheme.textPrimary, fontSize: 14, fontWeight: FontWeight.w650)),
        const SizedBox(height: 4),
        Text(subtitle, style: const TextStyle(color: AegisTheme.textMuted, fontSize: 10.5)),
        const SizedBox(height: 18),
        child,
      ],
    ),
  );
}

class _ThreatLandscapePanel extends StatelessWidget {
  const _ThreatLandscapePanel();

  @override
  Widget build(BuildContext context) => const _Panel(
    title: 'Threat landscape',
    subtitle: 'Detection volume and severity across connected environments',
    child: _EmptyPanelState(
      icon: Icons.query_stats_rounded,
      title: 'Waiting for security telemetry',
      message: 'Connect an authorized data source to populate trends. No sample events are shown.',
      height: 150,
    ),
  );
}

class _PriorityQueuePanel extends StatelessWidget {
  const _PriorityQueuePanel();

  @override
  Widget build(BuildContext context) => const _Panel(
    title: 'Priority queue',
    subtitle: 'Items requiring analyst attention',
    child: _EmptyPanelState(
      icon: Icons.inbox_outlined,
      title: 'Queue is not available yet',
      message: 'Verified alerts will appear here after integrations are authorized.',
      height: 150,
    ),
  );
}

class _IntegrationPanel extends StatelessWidget {
  const _IntegrationPanel();

  @override
  Widget build(BuildContext context) => const _Panel(
    title: 'Integration health',
    subtitle: 'Connected security tools and data pipelines',
    child: Row(
      children: [
        Icon(Icons.link_off_rounded, color: AegisTheme.warning, size: 19),
        SizedBox(width: 10),
        Expanded(child: Text(
          'No integrations connected. Configure approved sources in Settings before enabling monitoring.',
          style: TextStyle(color: AegisTheme.textMuted, fontSize: 11.5),
        )),
        Text('0 active', style: TextStyle(color: AegisTheme.textMuted, fontSize: 10, fontWeight: FontWeight.w600)),
      ],
    ),
  );
}

class _ActivityPanel extends StatelessWidget {
  const _ActivityPanel();

  @override
  Widget build(BuildContext context) => const _Panel(
    title: 'Recent activity',
    subtitle: 'Auditable actions across the engineer workspace',
    child: _EmptyPanelState(
      icon: Icons.history_rounded,
      title: 'No activity recorded',
      message: 'Activity will be displayed after authenticated services are connected.',
      height: 94,
    ),
  );
}

class _EmptyPanelState extends StatelessWidget {
  const _EmptyPanelState({
    required this.icon,
    required this.title,
    required this.message,
    required this.height,
  });

  final IconData icon;
  final String title;
  final String message;
  final double height;

  @override
  Widget build(BuildContext context) => SizedBox(
    height: height,
    width: double.infinity,
    child: Column(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        Icon(icon, color: AegisTheme.textMuted, size: 24),
        const SizedBox(height: 9),
        Text(title, style: const TextStyle(color: AegisTheme.textPrimary, fontSize: 11, fontWeight: FontWeight.w600)),
        const SizedBox(height: 5),
        ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 390),
          child: Text(message, textAlign: TextAlign.center,
            style: const TextStyle(color: AegisTheme.textMuted, fontSize: 10.5, height: 1.4)),
        ),
      ],
    ),
  );
}
