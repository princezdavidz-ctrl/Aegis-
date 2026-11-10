import 'package:flutter/material.dart';
import '../../../shared/widgets/feature_placeholder.dart';

class PatchCenterPage extends StatelessWidget {
  const PatchCenterPage({super.key});
  @override
  Widget build(BuildContext context) => const FeaturePlaceholder(
    title: 'Patch Center',
    description: 'Proposed patches, isolated test results and approval workflow.',
    icon: Icons.code,
  );
}
