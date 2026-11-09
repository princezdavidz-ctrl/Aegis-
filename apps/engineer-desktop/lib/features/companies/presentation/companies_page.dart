import 'package:flutter/material.dart';
import '../../../shared/widgets/feature_placeholder.dart';

class CompaniesPage extends StatelessWidget {
  const CompaniesPage({super.key});
  @override
  Widget build(BuildContext context) => const FeaturePlaceholder(
    title: 'Companies',
    description: 'Customer tenant directory, authorized scopes and integration health.',
    icon: Icons.business_outlined,
  );
}
