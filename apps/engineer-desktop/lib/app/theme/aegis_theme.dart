import 'package:flutter/material.dart';

class AegisTheme {
  static const background = Color(0xFF0B1220);
  static const surface = Color(0xFF111C2E);
  static const elevated = Color(0xFF18263B);
  static const accent = Color(0xFF60A5FA);
  static const textPrimary = Color(0xFFE5EDF8);
  static const textMuted = Color(0xFF94A3B8);
  static const border = Color(0xFF26364D);

  static ThemeData dark() => ThemeData(
    useMaterial3: true,
    brightness: Brightness.dark,
    colorScheme: ColorScheme.fromSeed(seedColor: accent, brightness: Brightness.dark, surface: surface),
    scaffoldBackgroundColor: background,
    cardColor: surface,
    dividerColor: border,
    appBarTheme: const AppBarTheme(backgroundColor: background, foregroundColor: textPrimary, elevation: 0),
  );
}
