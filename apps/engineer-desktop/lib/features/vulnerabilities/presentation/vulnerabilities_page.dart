import 'package:flutter/material.dart';
import '../../../shared/widgets/feature_placeholder.dart';

class VulnerabilitiesPage extends StatelessWidget {
  const VulnerabilitiesPage({super.key});
  @override
  Widget build(BuildContext context) => const FeaturePlaceholder(
        title: 'Vulnerabilities',
        description:
            'Findings, exposure context and remediation prioritization.',
        icon: Icons.bug_report_outlined,
      );
}
