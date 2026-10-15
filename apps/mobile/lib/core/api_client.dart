import 'package:dio/dio.dart';
import 'auth_store.dart';

class ApiClient {
  final AuthStore _authStore;
  late final Dio dio;

  ApiClient(this._authStore) {
    dio = Dio(
      BaseOptions(
        connectTimeout: const Duration(seconds: 5),
        receiveTimeout: const Duration(seconds: 60),
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
      ),
    );

    dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) async {
          final baseUrl = await _authStore.getApiBaseUrl();
          options.baseUrl = baseUrl;

          final token = await _authStore.getDeviceToken();
          if (token != null && token.isNotEmpty) {
            options.headers['Authorization'] = 'Bearer $token';
          }
          return handler.next(options);
        },
        onError: (DioException e, handler) {
          return handler.next(e);
        },
      ),
    );
  }
}
