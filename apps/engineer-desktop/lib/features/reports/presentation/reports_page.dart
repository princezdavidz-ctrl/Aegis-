import 'package:flutter/material.dart';
import '../../../shared/widgets/feature_placeholder.dart';

class ReportsPage extends StatelessWidget {
  const ReportsPage({super.key});
  @override
  Widget build(BuildContext context) => const FeaturePlaceholder(
        title: 'Reports',
        description:
            'Customer security posture and engineer operational reports.',
        icon: Icons.analytics_outlined,
      );
}
