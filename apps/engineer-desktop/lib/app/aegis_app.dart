import 'package:flutter/material.dart';
import 'router.dart';
import 'theme/aegis_theme.dart';

class AegisApp extends StatelessWidget {
  const AegisApp({super.key});

  @override
  Widget build(BuildContext context) => MaterialApp.router(
        title: 'AEGIS Engineer Desktop',
        debugShowCheckedModeBanner: false,
        theme: AegisTheme.dark(),
        routerConfig: aegisRouter,
      );
}
