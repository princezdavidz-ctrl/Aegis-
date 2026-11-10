import 'package:aegis_engineer_desktop/core/config/app_config.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('AppConfig.fromBaseUrl', () {
    test('accepts and normalizes an HTTPS API URL', () {
      final config = AppConfig.fromBaseUrl('  HTTPS://api.example.com/v1/  ');

      expect(config.apiBaseUrl, 'https://api.example.com/v1');
    });

    test('accepts the local development endpoint', () {
      final config = AppConfig.fromBaseUrl('http://127.0.0.1:8000');

      expect(config.apiBaseUrl, 'http://127.0.0.1:8000');
    });

    test('rejects relative URLs', () {
      expect(
        () => AppConfig.fromBaseUrl('/api'),
        throwsA(isA<FormatException>()),
      );
    });

    test('rejects unsupported URL schemes', () {
      expect(
        () => AppConfig.fromBaseUrl('ftp://api.example.com'),
        throwsA(isA<FormatException>()),
      );
    });

    test('rejects embedded credentials', () {
      expect(
        () => AppConfig.fromBaseUrl('https://user:password@api.example.com'),
        throwsA(isA<FormatException>()),
      );
    });

    test('rejects query parameters and fragments', () {
      expect(
        () => AppConfig.fromBaseUrl('https://api.example.com?token=secret'),
        throwsA(isA<FormatException>()),
      );
      expect(
        () => AppConfig.fromBaseUrl('https://api.example.com#section'),
        throwsA(isA<FormatException>()),
      );
    });
  });
}
