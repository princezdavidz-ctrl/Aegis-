import 'package:flutter/material.dart';

/// Shared visual tokens for the AEGIS engineer workstation.
class AegisTheme {
  static const background = Color(0xFF0B1220);
  static const surface = Color(0xFF111C2E);
  static const elevated = Color(0xFF18263B);
  static const accent = Color(0xFF55C7E8);
  static const accentSoft = Color(0xFF17384A);
  static const textPrimary = Color(0xFFE8EEF7);
  static const textMuted = Color(0xFF91A0B5);
  static const border = Color(0xFF26364D);
  static const success = Color(0xFF48C7A0);
  static const warning = Color(0xFFF0B75E);
  static const danger = Color(0xFFF07878);

  static ThemeData dark() {
    final scheme = ColorScheme.fromSeed(
      seedColor: accent,
      brightness: Brightness.dark,
      surface: surface,
    );
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      colorScheme: scheme.copyWith(
        primary: accent,
        secondary: accent,
        surface: surface,
        outline: border,
      ),
      scaffoldBackgroundColor: background,
      cardColor: surface,
      dividerColor: border,
      fontFamily: 'Inter',
      textTheme: const TextTheme(
        headlineMedium: TextStyle(
          color: textPrimary,
          fontSize: 26,
          fontWeight: FontWeight.w700,
          letterSpacing: -0.5,
        ),
        titleLarge: TextStyle(
          color: textPrimary,
          fontSize: 17,
          fontWeight: FontWeight.w600,
        ),
        titleMedium: TextStyle(
          color: textPrimary,
          fontSize: 14,
          fontWeight: FontWeight.w600,
        ),
        bodyLarge: TextStyle(color: textPrimary, fontSize: 14),
        bodyMedium: TextStyle(color: textMuted, fontSize: 13),
        labelMedium: TextStyle(
          color: textMuted,
          fontSize: 11,
          fontWeight: FontWeight.w600,
          letterSpacing: 0.5,
        ),
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: background,
        foregroundColor: textPrimary,
        elevation: 0,
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: elevated,
        hintStyle: const TextStyle(color: textMuted, fontSize: 13),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: border),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: border),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: accent, width: 1.3),
        ),
        contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
      ),
    );
  }
}
