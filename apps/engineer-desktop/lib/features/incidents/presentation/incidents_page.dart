import 'package:flutter/material.dart';
import '../../../shared/widgets/feature_placeholder.dart';

class IncidentsPage extends StatelessWidget {
  const IncidentsPage({super.key});
  @override
  Widget build(BuildContext context) => const FeaturePlaceholder(
        title: 'Incidents',
        description:
            'Incident cases, assignment, escalation and response tracking.',
        icon: Icons.assignment_outlined,
      );
}
