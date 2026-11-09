import 'package:flutter/material.dart';
import '../../../shared/widgets/feature_placeholder.dart';

class InvestigationsPage extends StatelessWidget {
  const InvestigationsPage({super.key});
  @override
  Widget build(BuildContext context) => const FeaturePlaceholder(
        title: 'Investigations',
        description:
            'Evidence, timelines, asset relationships and analyst notes.',
        icon: Icons.manage_search,
      );
}
