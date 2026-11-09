class AppConfig {
  const AppConfig({required this.apiBaseUrl});
  final String apiBaseUrl;

  factory AppConfig.fromEnvironment() {
    const value = String.fromEnvironment('AEGIS_API_BASE_URL', defaultValue: 'http://127.0.0.1:8000');
    final uri = Uri.tryParse(value);
    if (uri == null || !uri.hasScheme || uri.host.isEmpty) {
      throw const FormatException('AEGIS_API_BASE_URL must be an absolute URL.');
    }
    return AppConfig(apiBaseUrl: value);
  }
}
