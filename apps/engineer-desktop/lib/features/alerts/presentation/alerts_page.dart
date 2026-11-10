import 'package:flutter/material.dart';
import '../../../shared/widgets/feature_placeholder.dart';

class AlertsPage extends StatelessWidget {
  const AlertsPage({super.key});
  @override
  Widget build(BuildContext context) => const FeaturePlaceholder(
    title: 'Threat Alerts',
    description: 'Severity-based alert queue and triage workflow.',
    icon: Icons.notifications_active_outlined,
  );
}
