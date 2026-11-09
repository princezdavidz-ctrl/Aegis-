import 'package:dio/dio.dart';
import '../config/app_config.dart';

class AegisApiClient {
  AegisApiClient(AppConfig config) : dio = Dio(BaseOptions(
    baseUrl: config.apiBaseUrl,
    connectTimeout: const Duration(seconds: 10),
    receiveTimeout: const Duration(seconds: 20),
    sendTimeout: const Duration(seconds: 20),
    headers: const {'Accept': 'application/json'},
  ));

  final Dio dio;
}
