class AppConfig {
  const AppConfig({required this.apiBaseUrl});

  final String apiBaseUrl;

  /// Reads the API endpoint supplied at build/run time.
  ///
  /// Example:
  /// flutter run --dart-define=AEGIS_API_BASE_URL=https://api.example.com
  factory AppConfig.fromEnvironment() {
    const value = String.fromEnvironment(
      'AEGIS_API_BASE_URL',
      defaultValue: 'http://127.0.0.1:8000',
    );
    return AppConfig.fromBaseUrl(value);
  }

  /// Validates and normalizes an absolute HTTP(S) API URL.
  ///
  /// Credentials, query strings and fragments are rejected so secrets and
  /// endpoint-specific state are not embedded in application configuration.
  factory AppConfig.fromBaseUrl(String value) {
    final uri = Uri.tryParse(value.trim());
    if (uri == null ||
        !uri.isAbsolute ||
        !const {'http', 'https'}.contains(uri.scheme.toLowerCase()) ||
        uri.host.isEmpty ||
        uri.userInfo.isNotEmpty ||
        uri.hasQuery ||
        uri.hasFragment) {
      throw const FormatException(
        'AEGIS_API_BASE_URL must be an absolute HTTP(S) URL '
        'without credentials, query parameters or fragments.',
      );
    }

    var path = uri.path;
    while (path.endsWith('/')) {
      path = path.substring(0, path.length - 1);
    }
    final normalized = uri.replace(
      scheme: uri.scheme.toLowerCase(),
      path: path,
    );
    return AppConfig(apiBaseUrl: normalized.toString());
  }
}
