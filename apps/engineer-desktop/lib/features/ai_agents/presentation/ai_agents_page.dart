import 'package:flutter/material.dart';
import '../../../shared/widgets/feature_placeholder.dart';

class AiAgentsPage extends StatelessWidget {
  const AiAgentsPage({super.key});
  @override
  Widget build(BuildContext context) => const FeaturePlaceholder(
        title: 'AI Agents',
        description:
            'Agent status, evidence summaries and permissioned execution traces.',
        icon: Icons.smart_toy_outlined,
      );
}
