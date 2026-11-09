import 'package:flutter/material.dart';
import '../../app/theme/aegis_theme.dart';

class FeaturePlaceholder extends StatelessWidget {
  const FeaturePlaceholder({required this.title, required this.description, this.icon = Icons.construction_outlined, super.key});
  final String title;
  final String description;
  final IconData icon;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.all(32),
    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(title, style: Theme.of(context).textTheme.headlineMedium),
      const SizedBox(height: 8), Text(description), const SizedBox(height: 28),
      Expanded(child: Center(child: Container(
        constraints: const BoxConstraints(maxWidth: 560), padding: const EdgeInsets.all(32),
        decoration: BoxDecoration(color: AegisTheme.surface, borderRadius: BorderRadius.circular(16), border: Border.all(color: AegisTheme.border)),
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          Icon(icon, size: 42, color: AegisTheme.accent), const SizedBox(height: 16),
          Text('$title workspace', style: Theme.of(context).textTheme.titleLarge), const SizedBox(height: 8),
          const Text('This module is scaffolded. Connect it to authenticated AEGIS API services before showing live operational data.', textAlign: TextAlign.center),
          const SizedBox(height: 16), const Chip(label: Text('Integration pending')),
        ]),
      ))),
    ]),
  );
}
