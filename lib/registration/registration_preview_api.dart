import 'dart:convert';
import 'dart:math';

import 'package:http/http.dart' as http;
import '../services/demo_storage.dart';

class RegistrationPreviewError implements Exception {
  final String code;
  final String message;
  final String? field;
  const RegistrationPreviewError(this.code, this.message, [this.field]);
  @override
  String toString() => message;
}

abstract class RegistrationPreviewGateway {
  Future<Map<String, dynamic>> load();
  Future<List<Map<String, dynamic>>> locations();
  Future<Map<String, dynamic>> save(Map<String, dynamic> answers);
  Future<Map<String, dynamic>> challenge();
  Future<Map<String, dynamic>> verify(String code);
  Future<Map<String, dynamic>> complete();
  Future<Map<String, dynamic>> restart();
  Future<Map<String, dynamic>> newSession();
}

class RegistrationPreviewApi implements RegistrationPreviewGateway {
  static const storageKey = 'gpm.registration.preview.credentials.v1';
  final http.Client _client;
  final String baseUrl;
  final String? Function() readCredentials;
  final void Function(String value) writeCredentials;
  String? _id;
  String? _token;
  String? _completionKey;
  int? _completionRevision;
  Map<String, dynamic> _state = {};
  bool _storageAvailable = true;

  RegistrationPreviewApi({
    http.Client? client,
    this.baseUrl = 'https://app-api.gpmbot.ru/app-api/registration-preview',
    String? Function()? readCredentials,
    void Function(String value)? writeCredentials,
  }) : _client = client ?? http.Client(),
       readCredentials = readCredentials ?? (() => readDemoValue(storageKey)),
       writeCredentials =
           writeCredentials ?? ((value) => writeDemoValue(storageKey, value));

  Future<Map<String, dynamic>> _request(
    String method,
    String path, {
    Map<String, dynamic>? body,
    String? key,
  }) async {
    try {
      final request = http.Request(method, Uri.parse('$baseUrl$path'));
      request.headers.addAll({
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        if (_token != null) 'Authorization': 'Bearer $_token',
        if (key != null) 'Idempotency-Key': key,
      });
      if (body != null) request.body = jsonEncode(body);
      final streamed = await _client
          .send(request)
          .timeout(const Duration(seconds: 20));
      final response = await http.Response.fromStream(
        streamed,
      ).timeout(const Duration(seconds: 20));
      final decoded = jsonDecode(utf8.decode(response.bodyBytes));
      if (decoded is! Map<String, dynamic>) throw const FormatException();
      if (response.statusCode < 200 || response.statusCode >= 300) {
        final detail = decoded['detail'];
        if (detail is Map) {
          throw RegistrationPreviewError(
            detail['code']?.toString() ?? 'SERVER_ERROR',
            detail['message']?.toString() ?? 'Не удалось сохранить анкету',
            detail['field']?.toString(),
          );
        }
        throw const RegistrationPreviewError(
          'SERVER_ERROR',
          'Сервис временно недоступен. Попробуй еще раз',
        );
      }
      if (decoded['preview'] != true) {
        throw const RegistrationPreviewError(
          'WRONG_SERVICE',
          'Получен ответ другого сервиса',
        );
      }
      return decoded;
    } on RegistrationPreviewError {
      rethrow;
    } catch (_) {
      throw const RegistrationPreviewError(
        'NETWORK_ERROR',
        'Не удалось связаться с сервером. Введенные ответы остались на экране',
      );
    }
  }

  Map<String, dynamic> _accept(Map<String, dynamic> value) {
    _state = Map<String, dynamic>.from(value);
    return {..._state, 'browser_remembers_session': _storageAvailable};
  }

  @override
  Future<Map<String, dynamic>> load() async {
    try {
      final raw = readCredentials();
      if (raw != null && raw.isNotEmpty) {
        final saved = jsonDecode(raw);
        if (saved is! Map ||
            saved['id'] is! String ||
            saved['token'] is! String) {
          throw const FormatException();
        }
        _id = saved['id'];
        _token = saved['token'];
      }
    } catch (_) {
      _storageAvailable = false;
    }
    if (_id == null) return newSession();
    return _accept(
      await _request('GET', '/sessions/${Uri.encodeComponent(_id!)}'),
    );
  }

  @override
  Future<List<Map<String, dynamic>>> locations() async {
    final value = await _request('GET', '/locations');
    return (value['locations'] as List)
        .map((v) => Map<String, dynamic>.from(v as Map))
        .toList();
  }

  @override
  Future<Map<String, dynamic>> newSession() async {
    final result = await _request('POST', '/sessions');
    _id = result['registration_id'] as String;
    _token = result['session_token'] as String;
    _completionKey = null;
    _completionRevision = null;
    try {
      // Store credentials only. Answers and completion live in private server storage.
      writeCredentials(jsonEncode({'id': _id, 'token': _token}));
      _storageAvailable = true;
    } catch (_) {
      _storageAvailable = false;
    }
    return _accept(result);
  }

  @override
  Future<Map<String, dynamic>> save(Map<String, dynamic> answers) async =>
      _accept(
        await _request(
          'PATCH',
          '/sessions/${Uri.encodeComponent(_id!)}',
          body: {'expected_revision': _state['revision'], 'answers': answers},
        ),
      );

  Future<Map<String, dynamic>> _action(
    String action, {
    Map<String, dynamic> extra = const {},
    String? key,
  }) async => _accept(
    await _request(
      'POST',
      '/sessions/${Uri.encodeComponent(_id!)}/$action',
      body: {'expected_revision': _state['revision'], ...extra},
      key: key,
    ),
  );

  @override
  Future<Map<String, dynamic>> challenge() => _action('phone-challenge');
  @override
  Future<Map<String, dynamic>> verify(String code) =>
      _action('phone-verification', extra: {'code': code});
  @override
  Future<Map<String, dynamic>> restart() =>
      _action('restart', extra: {'confirmed': true});
  @override
  Future<Map<String, dynamic>> complete() {
    final revision = _state['revision'] as int;
    if (_completionKey == null || _completionRevision != revision) {
      _completionKey = List.generate(
        24,
        (_) => Random.secure().nextInt(256).toRadixString(16).padLeft(2, '0'),
      ).join();
      _completionRevision = revision;
    }
    return _action('complete', key: _completionKey);
  }
}
