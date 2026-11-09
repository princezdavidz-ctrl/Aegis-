import 'package:flutter/material.dart';
import '../../../shared/widgets/feature_placeholder.dart';

class MonitoringPage extends StatelessWidget {
  const MonitoringPage({super.key});
  @override
  Widget build(BuildContext context) => const FeaturePlaceholder(
        title: 'Live Monitoring',
        description: 'Live telemetry streams and security signal triage.',
        icon: Icons.monitor_heart_outlined,
      );
}
