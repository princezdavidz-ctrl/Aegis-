import 'package:flutter/material.dart';
import '../../../shared/widgets/feature_placeholder.dart';

class OverviewPage extends StatelessWidget {
  const OverviewPage({super.key});
  @override
  Widget build(BuildContext context) => const FeaturePlaceholder(
    title: 'Operations Overview',
    description: 'A consolidated view of authorized customer environments and SOC workload.',
    icon: Icons.dashboard_outlined,
  );
}
