import 'package:flutter/material.dart';
import '../../../shared/widgets/feature_placeholder.dart';

class SettingsPage extends StatelessWidget {
  const SettingsPage({super.key});
  @override
  Widget build(BuildContext context) => const FeaturePlaceholder(
    title: 'Settings',
    description: 'Desktop preferences, connection status and device controls.',
    icon: Icons.settings_outlined,
  );
}
