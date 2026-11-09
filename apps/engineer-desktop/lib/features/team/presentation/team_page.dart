import 'package:flutter/material.dart';
import '../../../shared/widgets/feature_placeholder.dart';

class TeamPage extends StatelessWidget {
  const TeamPage({super.key});
  @override
  Widget build(BuildContext context) => const FeaturePlaceholder(
    title: 'Team & Shifts',
    description: 'Engineer access, assignments, escalation and shift handover.',
    icon: Icons.groups_outlined,
  );
}
