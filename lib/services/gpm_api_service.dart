import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:http/http.dart' as http;

import 'demo_storage.dart';

class GpmApiService {
  static const sourceManual = 'manual';
  static const sourceExternal = 'external';
  static const sourceCrm = 'crm';
  static const demoWorkerId = 'worker-demo-1';
  static const _authTokenStorageKey = 'gpm_app_access_token_v1';
  static const _authUsernameStorageKey = 'gpm_app_username_v1';
  static const _authRoleStorageKey = 'gpm_app_role_v1';
  static const _requestTimeout = Duration(seconds: 15);
  static const demoWorkerName = 'Иван Петров';

  late String _appApiUrl;
  late String _appApiToken;
  late String _appMode;
  late String _appAccessToken;
  late String _appUsername;
  late String _appRole;
  void Function()? onSessionExpired;
  final List<Map<String, dynamic>> _demoOrders = [
    {
      'id': '1001',
      'title': 'Переезд офиса',
      'status': 'NEW',
      'address': 'ул. Ленина, 10',
      'workers_count': 3,
      'hours': 4,
      'description': 'Перевезти мебель и технику',
      'created_at': '2026-06-24T09:00:00.000Z',
      'assigned_worker_ids': <String>[],
    },
    {
      'id': '1002',
      'title': 'Разгрузка склада',
      'status': 'IN_PROCESS',
      'address': 'пр. Мира, 55',
      'workers_count': 2,
      'hours': 3,
      'description': 'Разгрузить фуру с товаром',
      'created_at': '2026-06-23T12:00:00.000Z',
      'assigned_worker_ids': <String>[demoWorkerId],
    },
    {
      'id': '1003',
      'title': 'Подъём стройматериалов',
      'status': 'CONVERTED',
      'address': 'ул. Строителей, 7',
      'workers_count': 4,
      'hours': 6,
      'description': 'Поднять кирпич на 5 этаж',
      'created_at': '2026-06-22T08:30:00.000Z',
      'assigned_worker_ids': <String>[demoWorkerId],
    },
  ];

  final List<Map<String, dynamic>> _demoApplications = [
    {
      'id': 'app-1002-1',
      'order_id': '1002',
      'worker_id': demoWorkerId,
      'worker_name': demoWorkerName,
      'status': 'APPROVED',
      'created_at': '2026-06-23T12:15:00.000Z',
    },
    {
      'id': 'app-1003-1',
      'order_id': '1003',
      'worker_id': demoWorkerId,
      'worker_name': demoWorkerName,
      'status': 'APPROVED',
      'created_at': '2026-06-22T08:45:00.000Z',
    },
  ];

  final Map<String, Map<String, dynamic>> _demoWorkers = {
    demoWorkerId: {
      'id': demoWorkerId,
      'full_name': demoWorkerName,
      'phone_number': '+7 900 123-45-67',
      'telegram': '@ivan_loader',
      'date_birth': '15.04.1994',
      'nationality': true,
      'cities': <String>['Москва', 'Химки'],
      'tools': {'straps': true, 'tools': true},
      'employment_type': 'contract',
      'inn': '772812345678',
      'passport': '4512 345678',
      'card_last4': '',
      'payout_method': 'account',
      'payout_account': '',
      'payout_bik': '',
      'address_city': 'Москва',
      'address_street': '',
      'address_house': '',
      'address_apartment': '',
      'address': '',
      'mark': 'Нет',
      'success_requests': 8,
      'fail_requests': 1,
      'rating': 14,
    },
  };

  GpmApiService() {
    _appApiUrl = dotenv.env['GPM_APP_API_URL'] ?? '';
    _appApiToken = dotenv.env['GPM_APP_API_TOKEN'] ?? '';
    _appMode = (dotenv.env['GPM_APP_MODE'] ?? 'demo').trim().toLowerCase();
    _appAccessToken = readDemoValue(_authTokenStorageKey) ?? '';
    _appUsername = readDemoValue(_authUsernameStorageKey) ?? '';
    _appRole = readDemoValue(_authRoleStorageKey) ?? 'logist';
    // Не бросаем исключение если backend не задан — работаем в демо-режиме
    if (usesLocalPersistence) {
      _loadDemoState();
    } else {
      _demoOrders.clear();
      _demoApplications.clear();
    }
  }

  bool get isConfigured => hasAppBackend;
  bool get isApiMode => _appMode == 'api' || _appMode == 'production';
  bool get hasAppBackend => _appApiUrl.trim().isNotEmpty;
  bool get usesLocalPersistence => !isApiMode || !hasAppBackend;
  bool get requiresAuth => isApiMode && hasAppBackend;
  bool get hasAuthSession => !requiresAuth || _appAccessToken.trim().isNotEmpty;
  String get currentUsername => _appUsername;
  String get currentRole => _appRole;

  Future<Map<String, dynamic>> registerWithInvitation({
    required String invitation,
    required String password,
    required String passwordConfirmation,
    required String role,
  }) async {
    if (_appApiUrl.trim().isEmpty) {
      return {'success': false, 'error': 'GPM_APP_API_URL не задан'};
    }
    try {
      final response = await http
          .post(
            Uri.parse(_appApiUrl).resolve('/app-api/auth/register'),
            headers: const {
              'Accept': 'application/json',
              'Content-Type': 'application/json',
            },
            body: jsonEncode({
              'invitation': invitation.trim(),
              'password': password,
              'password_confirmation': passwordConfirmation,
              'role': role,
            }),
          )
          .timeout(_requestTimeout);
      final decoded = jsonDecode(response.body);
      if (response.statusCode < 200 || response.statusCode >= 300) {
        final detail = decoded is Map
            ? decoded['detail']?.toString() ?? ''
            : '';
        return {
          'success': false,
          'error': detail == 'invalid or expired invitation'
              ? 'Приглашение недействительно, уже использовано или истекло.'
              : 'Не удалось принять приглашение',
        };
      }
      if (decoded is! Map || decoded['success'] != true) {
        return {'success': false, 'error': 'Некорректный ответ сервера'};
      }
      final registeredRole = decoded['role']?.toString() ?? '';
      if (registeredRole != role) {
        return {
          'success': false,
          'error': 'Приглашение относится к другой роли',
        };
      }
      return {
        'success': true,
        'username': decoded['username']?.toString() ?? '',
        'role': registeredRole,
      };
    } on TimeoutException {
      return {
        'success': false,
        'error': 'Сервер не ответил вовремя. Попробуйте ещё раз.',
      };
    } catch (_) {
      return {'success': false, 'error': 'Не удалось принять приглашение'};
    }
  }

  Future<Map<String, dynamic>> login({
    required String username,
    required String password,
    required String role,
  }) async {
    if (_appApiUrl.trim().isEmpty) {
      return {'success': false, 'error': 'GPM_APP_API_URL не задан'};
    }

    try {
      final response = await http
          .post(
            Uri.parse(_appApiUrl).resolve('/app-api/auth/login'),
            headers: const {
              'Accept': 'application/json',
              'Content-Type': 'application/json',
            },
            body: jsonEncode({
              'username': username.trim(),
              'password': password,
              'role': role,
            }),
          )
          .timeout(_requestTimeout);
      if (response.statusCode < 200 || response.statusCode >= 300) {
        return {
          'success': false,
          'error': 'Ошибка входа: ${response.statusCode}',
        };
      }

      final decoded = jsonDecode(response.body);
      if (decoded is! Map) {
        return {'success': false, 'error': 'Некорректный ответ сервера'};
      }
      final token = decoded['access_token']?.toString() ?? '';
      if (token.isEmpty) {
        return {'success': false, 'error': 'Сервер не вернул токен'};
      }
      final authenticatedRole = decoded['role']?.toString() ?? '';
      if (!const {'client', 'worker', 'logist'}.contains(authenticatedRole)) {
        return {'success': false, 'error': 'Сервер вернул некорректную роль'};
      }
      if (authenticatedRole != role) {
        return {
          'success': false,
          'error': 'Эта учётная запись относится к другой роли.',
        };
      }

      _appAccessToken = token;
      _appUsername = decoded['username']?.toString() ?? username.trim();
      _appRole = authenticatedRole;
      writeDemoValue(_authTokenStorageKey, _appAccessToken);
      writeDemoValue(_authUsernameStorageKey, _appUsername);
      writeDemoValue(_authRoleStorageKey, _appRole);
      return {'success': true};
    } on TimeoutException {
      return {
        'success': false,
        'error':
            'Сервер не ответил вовремя. Проверьте подключение и повторите.',
      };
    } catch (error) {
      return {'success': false, 'error': error.toString()};
    }
  }

  Future<void> logout() async {
    final accessToken = _appAccessToken.trim();
    _clearLocalSession();
    if (!isApiMode || _appApiUrl.trim().isEmpty || accessToken.isEmpty) {
      return;
    }
    try {
      await http
          .post(
            Uri.parse(_appApiUrl).resolve('/app-api/auth/logout'),
            headers: {
              'Accept': 'application/json',
              'Authorization': 'Bearer $accessToken',
            },
          )
          .timeout(_requestTimeout);
    } catch (_) {
      // The local session is already cleared. An expired or unreachable server
      // session will become unusable at its normal expiry time.
    }
  }

  void _clearLocalSession() {
    _appAccessToken = '';
    _appUsername = '';
    _appRole = 'logist';
    removeDemoValue(_authTokenStorageKey);
    removeDemoValue(_authUsernameStorageKey);
    removeDemoValue(_authRoleStorageKey);
    if (isApiMode) {
      // Production does not have server-backed profiles/chats yet. Remove their
      // local copies so the next account on this device cannot see them.
      for (final key in const [
        'gpm_chat_state_v1',
        'gpm.client.profile.v1',
        'gpm.logist.profile.v1',
        'gpm_demo_state_v1',
      ]) {
        removeDemoValue(key);
      }
    }
  }

  Map<String, String> get _authenticatedHeaders => {
    'Accept': 'application/json',
    'Authorization': 'Bearer ${_appAccessToken.trim()}',
    'Content-Type': 'application/json',
  };

  Future<Map<String, dynamic>> _authenticatedJsonRequest(
    String path, {
    String method = 'GET',
    Map<String, dynamic>? body,
  }) async {
    if (_appApiUrl.trim().isEmpty || _appAccessToken.trim().isEmpty) {
      throw StateError('Требуется вход');
    }
    final uri = Uri.parse(_appApiUrl).resolve(path);
    late http.Response response;
    try {
      response = switch (method) {
        'POST' =>
          await http
              .post(
                uri,
                headers: _authenticatedHeaders,
                body: jsonEncode(body ?? const <String, dynamic>{}),
              )
              .timeout(_requestTimeout),
        'PATCH' =>
          await http
              .patch(
                uri,
                headers: _authenticatedHeaders,
                body: jsonEncode(body ?? const <String, dynamic>{}),
              )
              .timeout(_requestTimeout),
        _ =>
          await http
              .get(uri, headers: _authenticatedHeaders)
              .timeout(_requestTimeout),
      };
    } on TimeoutException {
      throw StateError('Сервер не ответил вовремя');
    }
    if (response.statusCode == 401 || response.statusCode == 403) {
      _clearLocalSession();
      onSessionExpired?.call();
      throw StateError('Сессия истекла. Войдите снова');
    }
    dynamic decoded;
    try {
      decoded = response.body.isEmpty
          ? <String, dynamic>{}
          : jsonDecode(response.body);
    } catch (_) {
      throw StateError('Сервер вернул некорректный ответ');
    }
    if (response.statusCode < 200 || response.statusCode >= 300) {
      final detail = decoded is Map ? decoded['detail']?.toString() : null;
      throw StateError(
        detail?.isNotEmpty == true
            ? detail!
            : 'Ошибка сервера: ${response.statusCode}',
      );
    }
    if (decoded is Map<String, dynamic>) return decoded;
    if (decoded is Map) {
      return decoded.map((key, value) => MapEntry(key.toString(), value));
    }
    throw StateError('Сервер вернул некорректный ответ');
  }

  Future<Map<String, dynamic>> getMyProfile() async {
    final response = await _authenticatedJsonRequest('/app-api/me/profile');
    final profile = response['profile'];
    if (profile is Map<String, dynamic>) return profile;
    if (profile is Map) {
      return profile.map((key, value) => MapEntry(key.toString(), value));
    }
    throw StateError('Сервер не вернул профиль');
  }

  Future<Map<String, dynamic>> updateMyProfile(
    Map<String, dynamic> patch,
  ) async {
    final response = await _authenticatedJsonRequest(
      '/app-api/me/profile',
      method: 'PATCH',
      body: patch,
    );
    final profile = response['profile'];
    if (profile is Map<String, dynamic>) return profile;
    if (profile is Map) {
      return profile.map((key, value) => MapEntry(key.toString(), value));
    }
    throw StateError('Сервер не вернул профиль');
  }

  Future<List<Map<String, dynamic>>> getMyVerifications() async {
    final response = await _authenticatedJsonRequest(
      '/app-api/me/verifications',
    );
    return _mapList(response['submissions']);
  }

  Future<Map<String, dynamic>> submitMyVerification({
    required String verificationType,
    required Map<String, dynamic> data,
    Uint8List? attachmentBytes,
    String? attachmentName,
    String? attachmentMediaType,
  }) async {
    if (attachmentBytes != null && attachmentBytes.length > 8 * 1024 * 1024) {
      throw StateError('Размер фотографии не должен превышать 8 МБ');
    }
    final response = await _authenticatedJsonRequest(
      '/app-api/me/verifications/${Uri.encodeComponent(verificationType)}',
      method: 'POST',
      body: {
        'data': data,
        if (attachmentBytes != null)
          'attachment': {
            'filename': attachmentName ?? 'passport.jpg',
            'media_type': attachmentMediaType ?? 'image/jpeg',
            'base64': base64Encode(attachmentBytes),
          },
      },
    );
    return _requiredMap(response['submission'], 'Сервер не вернул заявку');
  }

  Future<List<Map<String, dynamic>>> getWorkerVerificationQueue() async {
    final response = await _authenticatedJsonRequest(
      '/app-api/logist/worker-verifications',
    );
    return _mapList(response['submissions']);
  }

  Future<void> reviewWorkerVerification({
    required String submissionId,
    required bool approved,
    String rejectionReason = '',
  }) async {
    await _authenticatedJsonRequest(
      '/app-api/logist/worker-verifications/${Uri.encodeComponent(submissionId)}',
      method: 'PATCH',
      body: {
        'status': approved ? 'verified' : 'rejected',
        'rejection_reason': approved ? '' : rejectionReason.trim(),
      },
    );
  }

  Future<Uint8List> downloadWorkerVerificationAttachment(
    String submissionId,
  ) async {
    if (_appApiUrl.trim().isEmpty || _appAccessToken.trim().isEmpty) {
      throw StateError('Требуется вход');
    }
    final response = await http
        .get(
          Uri.parse(_appApiUrl).resolve(
            '/app-api/logist/worker-verifications/'
            '${Uri.encodeComponent(submissionId)}/attachment',
          ),
          headers: {
            'Accept': 'image/jpeg,image/png',
            'Authorization': 'Bearer ${_appAccessToken.trim()}',
          },
        )
        .timeout(_requestTimeout);
    if (response.statusCode == 401 || response.statusCode == 403) {
      _clearLocalSession();
      onSessionExpired?.call();
      throw StateError('Сессия истекла. Войдите снова');
    }
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw StateError('Не удалось загрузить вложение');
    }
    return response.bodyBytes;
  }

  static List<Map<String, dynamic>> _mapList(dynamic value) {
    if (value is! List) return const [];
    return value
        .whereType<Map>()
        .map(
          (item) => item.map((key, value) => MapEntry(key.toString(), value)),
        )
        .toList();
  }

  static Map<String, dynamic> _requiredMap(dynamic value, String error) {
    if (value is Map<String, dynamic>) return value;
    if (value is Map) {
      return value.map((key, item) => MapEntry(key.toString(), item));
    }
    throw StateError(error);
  }

  Future<Map<String, dynamic>> getMyDashboard() {
    return _authenticatedJsonRequest('/app-api/me/dashboard');
  }

  Future<Map<String, dynamic>> getMyFinance() {
    return _authenticatedJsonRequest('/app-api/me/finance');
  }

  Future<List<Map<String, dynamic>>> getMyChatThreads() async {
    final response = await _authenticatedJsonRequest('/app-api/me/chats');
    final threads = response['threads'];
    if (threads is! List) return const [];
    return threads
        .whereType<Map>()
        .map(
          (item) => item.map((key, value) => MapEntry(key.toString(), value)),
        )
        .toList();
  }

  Future<Map<String, dynamic>> getMyChatConversation(String threadId) {
    return _authenticatedJsonRequest(
      '/app-api/me/chats/${Uri.encodeComponent(threadId)}',
    );
  }

  Future<Map<String, dynamic>> sendMyChatMessage(String threadId, String text) {
    return _authenticatedJsonRequest(
      '/app-api/me/chats/${Uri.encodeComponent(threadId)}/messages',
      method: 'POST',
      body: {'text': text},
    );
  }

  Future<void> requestMyChatSupport(String threadId) async {
    await _authenticatedJsonRequest(
      '/app-api/me/chats/${Uri.encodeComponent(threadId)}/support',
      method: 'POST',
    );
  }

  Future<void> setMyChatAttention(
    String threadId,
    bool requiresAttention,
  ) async {
    await _authenticatedJsonRequest(
      '/app-api/me/chats/${Uri.encodeComponent(threadId)}/attention',
      method: 'PATCH',
      body: {'requires_attention': requiresAttention},
    );
  }

  Future<List<Map<String, dynamic>>> suggestAddresses({
    required String query,
    String city = '',
  }) async {
    if (_appApiUrl.trim().isEmpty || _appAccessToken.trim().isEmpty) {
      throw StateError('Сервис адресов не настроен');
    }

    final response = await http
        .post(
          Uri.parse(_appApiUrl).resolve('/app-api/me/address-suggestions'),
          headers: {
            'Accept': 'application/json',
            'Authorization': 'Bearer ${_appAccessToken.trim()}',
            'Content-Type': 'application/json',
          },
          body: jsonEncode({'query': query.trim(), 'city': city.trim()}),
        )
        .timeout(_requestTimeout);

    if (response.statusCode == 401 || response.statusCode == 403) {
      _clearLocalSession();
      onSessionExpired?.call();
      throw StateError('Сессия истекла. Войдите снова');
    }
    if (response.statusCode < 200 || response.statusCode >= 300) {
      var message = 'Сервис адресов временно недоступен';
      try {
        final decoded = jsonDecode(response.body);
        if (decoded is Map && decoded['detail'] != null) {
          message = decoded['detail'].toString();
        }
      } catch (_) {}
      throw StateError(message);
    }

    final decoded = jsonDecode(response.body);
    final suggestions = decoded is Map ? decoded['suggestions'] : null;
    if (suggestions is! List) return const [];
    return suggestions
        .whereType<Map>()
        .map(
          (item) => item.map((key, value) => MapEntry(key.toString(), value)),
        )
        .toList();
  }

  bool isExternalOrder(Map<String, dynamic> order) {
    return _isExternalSource(order['source']);
  }

  bool _isExternalSource(dynamic source) {
    final value = source?.toString().toLowerCase();
    return value == sourceExternal || value == sourceCrm;
  }

  String _normalizeOrderSource(dynamic source) {
    return _isExternalSource(source) ? sourceExternal : sourceManual;
  }

  Future<Map<String, dynamic>> importExternalOrder(
    Map<String, dynamic> payload,
  ) async {
    return importCrmOrder(payload);
  }

  Future<Map<String, dynamic>> importCrmOrder(
    Map<String, dynamic> payload,
  ) async {
    try {
      final orderData = _mapValue(payload['order_data']);
      final completionDate = _mapValue(orderData['completion_date']);
      final loaders = _mapValue(orderData['loaders']);
      final info = _mapValue(orderData['info']);
      final externalOrderId = _stringValue(
        orderData['order_number'],
        fallback: 'CRM-${DateTime.now().millisecondsSinceEpoch}',
      );
      final existingIndex = _demoOrders.indexWhere(
        (order) => order['external_order_id']?.toString() == externalOrderId,
      );

      if (existingIndex != -1) {
        return {
          'success': true,
          'orderId': _demoOrders[existingIndex]['id'],
          'duplicate': true,
        };
      }

      final additionalInfo = _stringValue(info['additional']);
      final national = _nationalFromOrderData(
        orderData['national'] ?? orderData['nationality'],
        additionalInfo,
      );

      return createOrder(
        title: 'Заявка № $externalOrderId',
        address: _stringValue(
          info['address'],
          fallback: _stringValue(
            info['address_street'],
            fallback: 'Адрес не указан',
          ),
        ),
        workersCount: _intValue(loaders['loader_count'], fallback: 1),
        hours: _intValue(
          orderData['hours'],
          fallback: _intValue(orderData['min_time'], fallback: 4),
        ),
        description: _stringValue(orderData['note']),
        clientEmail: _stringValue(
          payload['client_email'],
          fallback: 'crm@gpm.ru',
        ),
        clientPhone: _stringValue(payload['client_phone']),
        scheduledAt: _stringValue(
          completionDate['date'],
          fallback: DateTime.now().toUtc().toIso8601String(),
        ),
        city: _stringValue(
          orderData['city'],
          fallback: _stringValue(payload['city'], fallback: 'Москва'),
        ),
        source: sourceExternal,
        externalOrderId: externalOrderId,
        metro: _stringValue(info['metro_station']),
        national: national,
        minTime: _intValue(orderData['min_time'], fallback: 4),
        pricePerHour: _intOrNull(orderData['price_per_hour']),
        priceRegular: _intOrNull(orderData['price_regular']),
        priceState: _intOrNull(orderData['price_state']),
        individualPrice: _intOrNull(orderData['individual_price']),
        legalPrice: _intOrNull(orderData['legal_price']),
        nationality: national == 'yes'
            ? 'ru'
            : national == 'no'
            ? 'non_ru'
            : 'any',
        workerCategory: _stringValue(
          orderData['worker_category'],
          fallback: 'loader',
        ),
        workMode: _stringValue(orderData['work_mode'], fallback: 'rate'),
        shiftDescription: _stringValue(orderData['shift_description']),
        telegramUsername: _stringValue(
          payload['telegram_username'],
        ).replaceFirst('@', ''),
        timezone: _stringValue(
          orderData['timezone'],
          fallback: 'Europe/Moscow',
        ),
        additionalInfo: additionalInfo,
        addressStreet: _stringValue(
          info['address_street'],
          fallback: _stringValue(info['address']),
        ),
        addressNumber: _stringValue(info['address_number']),
        addressLat: _doubleOrNull(info['address_lat']),
        addressLon: _doubleOrNull(info['address_lon']),
      );
    } catch (error) {
      return {'success': false, 'error': error.toString()};
    }
  }

  Future<Map<String, dynamic>> createOrder({
    required String title,
    required String address,
    required int workersCount,
    required int hours,
    required String description,
    required String clientEmail,
    required String clientPhone,
    String? scheduledAt,
    String? city,
    String source = 'manual',
    String? externalOrderId,
    String? metro,
    String? national,
    int? minTime,
    int? pricePerHour,
    int? priceRegular,
    int? priceState,
    int? individualPrice,
    int? legalPrice,
    String? nationality,
    String? workerCategory,
    String? workMode,
    String? shiftDescription,
    String? telegramUsername,
    String? timezone,
    String? additionalInfo,
    String? addressStreet,
    String? addressNumber,
    double? addressLat,
    double? addressLon,
  }) async {
    final effectiveSource = _normalizeOrderSource(source);
    final effectiveExternalOrderId = externalOrderId?.trim().isNotEmpty == true
        ? externalOrderId!.trim()
        : effectiveSource == sourceExternal
        ? null
        : _generateManualOrderNumber();
    final effectiveScheduledAt =
        scheduledAt ?? DateTime.now().toUtc().toIso8601String();
    final effectiveMinTime = minTime ?? hours;
    final effectiveAdditional = [
      if (additionalInfo?.trim().isNotEmpty == true) additionalInfo!.trim(),
      if (national == 'yes') 'Только РФ',
      if (national == 'no') 'Только не РФ',
      if (workMode == 'shift' && shiftDescription?.trim().isNotEmpty == true)
        shiftDescription!.trim(),
    ].join('\n');
    final externalPayload = {
      'source': effectiveSource,
      'source_system': 'gpm-app',
      'telegram_username': (telegramUsername ?? '').replaceFirst('@', ''),
      'client_email': clientEmail,
      'client_phone': clientPhone,
      'city': city,
      'order_data': {
        'order_number': effectiveExternalOrderId ?? title,
        'completion_date': {'date': effectiveScheduledAt},
        'timezone': timezone ?? 'Europe/Moscow',
        'loaders': {'loader_count': workersCount},
        'info': {
          'address': address,
          'address_street': addressStreet ?? address,
          'address_number': addressNumber ?? '',
          'address_lat': addressLat,
          'address_lon': addressLon,
          'metro_station': metro,
          'additional': effectiveAdditional,
        },
        'note': description,
        'min_time': effectiveMinTime,
        'hours': hours,
        'national': national,
        'nationality': nationality,
        'work_mode': workMode,
        'worker_category': workerCategory,
        'price_per_hour': pricePerHour,
        'price_regular': priceRegular,
        'price_state': priceState,
        'individual_price': individualPrice,
        'legal_price': legalPrice,
        'shift_description': shiftDescription,
      },
    };

    if ((isApiMode && hasAppBackend) || effectiveSource == sourceExternal) {
      final published = await _publishAppOrder(externalPayload);
      if (published['success'] == true) {
        final returnedOrder = published['order'];
        if (returnedOrder is Map) {
          _upsertOrder(
            returnedOrder.map((key, value) => MapEntry(key.toString(), value)),
          );
        } else {
          try {
            await _syncAppPublishedOrders();
          } catch (_) {
            // The POST was confirmed by the server. A later refresh can retry
            // synchronization without encouraging the user to create a duplicate.
          }
        }
        final publishedOrderId = published['order_number']?.toString();
        return {
          'success': true,
          'orderId': publishedOrderId?.isNotEmpty == true
              ? publishedOrderId
              : effectiveExternalOrderId ?? title,
          'published': true,
        };
      }

      if (_appApiUrl.trim().isNotEmpty) {
        return published;
      }
    }

    // Демо-режим если backend не настроен
    {
      final orderId =
          effectiveExternalOrderId ??
          DateTime.now().microsecondsSinceEpoch.toString();
      final effectiveTitle = effectiveExternalOrderId == null
          ? title
          : title.contains(effectiveExternalOrderId)
          ? title
          : 'Заявка № $effectiveExternalOrderId';
      _demoOrders.insert(0, {
        'id': orderId,
        'title': effectiveTitle,
        'status': 'NEW',
        'address': address,
        'workers_count': workersCount,
        'hours': hours,
        'description': description,
        'client_email': clientEmail,
        'client_phone': clientPhone,
        'scheduled_at': effectiveScheduledAt,
        'city': city,
        'source': effectiveSource,
        'created_by_role': _appRole,
        'external_order_id': effectiveExternalOrderId,
        'metro': metro,
        'national': national,
        'min_time': effectiveMinTime,
        'price_per_hour': pricePerHour,
        'price_regular': priceRegular,
        'price_state': priceState,
        'individual_price': individualPrice,
        'legal_price': legalPrice,
        'nationality': nationality,
        'worker_category': workerCategory,
        'work_mode': workMode,
        'shift_description': shiftDescription,
        'telegram_username': telegramUsername,
        'timezone': timezone ?? 'Europe/Moscow',
        'additional_info': additionalInfo,
        'address_street': addressStreet ?? address,
        'address_number': addressNumber,
        'address_lat': addressLat,
        'address_lon': addressLon,
        'source_payload': externalPayload,
        'created_at': DateTime.now().toUtc().toIso8601String(),
        'assigned_worker_ids': <String>[],
      });
      _saveDemoState();
      return {'success': true, 'orderId': orderId};
    }
  }

  Future<Map<String, dynamic>> _publishAppOrder(
    Map<String, dynamic> payload,
  ) async {
    if (_appApiUrl.trim().isEmpty) {
      return {'success': false, 'error': 'GPM_APP_API_URL не задан'};
    }

    final uri = Uri.parse(
      _appApiUrl,
    ).resolve(isApiMode ? '/app-api/me/orders' : '/app-api/orders');
    final headers = <String, String>{
      'Accept': 'application/json',
      'Content-Type': 'application/json',
    };
    if (isApiMode) {
      if (_appAccessToken.trim().isEmpty) {
        return {'success': false, 'error': 'Требуется вход'};
      }
      headers['Authorization'] = 'Bearer ${_appAccessToken.trim()}';
    } else if (_appApiToken.trim().isNotEmpty) {
      headers['X-GPM-App-Token'] = _appApiToken.trim();
    }

    try {
      final response = await http
          .post(uri, headers: headers, body: jsonEncode(payload))
          .timeout(_requestTimeout);
      if (response.statusCode == 401 || response.statusCode == 403) {
        if (isApiMode) {
          _clearLocalSession();
          onSessionExpired?.call();
        }
        return {'success': false, 'error': 'Сессия истекла. Войдите снова.'};
      }
      if (response.statusCode < 200 || response.statusCode >= 300) {
        return {
          'success': false,
          'error': 'Не удалось создать заказ: ${response.statusCode}',
        };
      }

      final decoded = jsonDecode(response.body);
      if (decoded is Map<String, dynamic>) {
        return decoded;
      }
      if (decoded is Map) {
        return decoded.map((key, value) => MapEntry(key.toString(), value));
      }
      return {'success': true};
    } on TimeoutException {
      return {
        'success': false,
        'error': 'Сервер не ответил вовремя. Заказ не был подтвержден.',
      };
    } catch (error) {
      return {'success': false, 'error': error.toString()};
    }
  }

  String _generateManualOrderNumber() {
    final now = DateTime.now();
    final year = (now.year % 100).toString().padLeft(2, '0');
    final month = now.month.toString().padLeft(2, '0');
    final day = now.day.toString().padLeft(2, '0');
    final hour = now.hour.toString().padLeft(2, '0');
    final minute = now.minute.toString().padLeft(2, '0');
    final second = now.second.toString().padLeft(2, '0');
    final millisecond = now.millisecond.toString().padLeft(3, '0');
    return 'APP-$year$month$day-$hour$minute$second$millisecond';
  }

  Future<List<Map<String, dynamic>>> getOrders() async {
    await _syncAppPublishedOrders();
    if (!isApiMode) {
      _normalizeDemoCrmOrders();
    }
    return _demoOrders
        .map((order) => Map<String, dynamic>.from(order))
        .toList();
  }

  Future<void> _syncAppPublishedOrders() async {
    if (_appApiUrl.trim().isEmpty) return;
    if (requiresAuth && _appAccessToken.trim().isEmpty) return;

    final uri = Uri.parse(
      _appApiUrl,
    ).resolve(isApiMode ? '/app-api/me/orders' : '/app-api/orders');
    final headers = <String, String>{'Accept': 'application/json'};
    if (isApiMode) {
      headers['Authorization'] = 'Bearer ${_appAccessToken.trim()}';
    } else if (_appApiToken.trim().isNotEmpty) {
      headers['X-GPM-App-Token'] = _appApiToken.trim();
    }

    try {
      final response = await http
          .get(uri, headers: headers)
          .timeout(_requestTimeout);
      if (response.statusCode == 401 || response.statusCode == 403) {
        if (isApiMode) {
          _clearLocalSession();
          onSessionExpired?.call();
        }
        throw StateError('Сессия истекла. Войдите снова.');
      }
      if (response.statusCode < 200 || response.statusCode >= 300) {
        throw StateError('Не удалось загрузить заказы: ${response.statusCode}');
      }

      final decoded = jsonDecode(response.body);
      final orders = decoded is Map ? decoded['orders'] : decoded;
      if (orders is! List) {
        throw const FormatException(
          'Сервер вернул некорректный список заказов',
        );
      }

      if (isApiMode) {
        _demoOrders.clear();
      }
      for (final order in orders.whereType<Map>()) {
        final mappedOrder = order.map(
          (key, value) => MapEntry(key.toString(), value),
        );
        if (!isApiMode &&
            (mappedOrder['order_data'] is Map ||
                mappedOrder['order_data'] is String)) {
          await importExternalOrder(mappedOrder);
        } else {
          _upsertOrder(mappedOrder);
        }
      }
    } catch (_) {
      if (isApiMode) rethrow;
    }
  }

  Future<Map<String, dynamic>> _patchAppOrder(
    String orderId,
    Map<String, dynamic> patch,
  ) async {
    if (_appApiUrl.trim().isEmpty) {
      return {'success': false, 'error': 'GPM_APP_API_URL не задан'};
    }

    final uri = Uri.parse(_appApiUrl).resolve(
      isApiMode ? '/app-api/me/orders/$orderId' : '/app-api/orders/$orderId',
    );
    final headers = <String, String>{
      'Accept': 'application/json',
      'Content-Type': 'application/json',
    };
    if (isApiMode) {
      if (_appAccessToken.trim().isEmpty) {
        return {'success': false, 'error': 'Требуется вход'};
      }
      headers['Authorization'] = 'Bearer ${_appAccessToken.trim()}';
    } else if (_appApiToken.trim().isNotEmpty) {
      headers['X-GPM-App-Token'] = _appApiToken.trim();
    }

    try {
      final response = await http
          .patch(uri, headers: headers, body: jsonEncode(patch))
          .timeout(_requestTimeout);
      if (response.statusCode == 401 || response.statusCode == 403) {
        if (isApiMode) {
          _clearLocalSession();
          onSessionExpired?.call();
        }
        return {'success': false, 'error': 'Сессия истекла. Войдите снова.'};
      }
      if (response.statusCode < 200 || response.statusCode >= 300) {
        return {
          'success': false,
          'error': 'Не удалось изменить заказ: ${response.statusCode}',
        };
      }

      final decoded = jsonDecode(response.body);
      if (decoded is Map<String, dynamic>) {
        return decoded;
      }
      if (decoded is Map) {
        return decoded.map((key, value) => MapEntry(key.toString(), value));
      }
      return {'success': true};
    } on TimeoutException {
      return {
        'success': false,
        'error': 'Сервер не ответил вовремя. Изменение не подтверждено.',
      };
    } catch (error) {
      return {'success': false, 'error': error.toString()};
    }
  }

  Future<Map<String, dynamic>> updateOrderDraft(
    String orderId,
    Map<String, dynamic> patch,
  ) async {
    final result = await _patchAppOrder(orderId, patch);
    if (result['success'] == true) {
      await _syncAppPublishedOrders();
    }
    return result;
  }

  void _upsertOrder(Map<String, dynamic> order) {
    final externalOrderId = _stringValue(order['external_order_id']);
    final id = _stringValue(order['id'], fallback: externalOrderId);
    if (_isInvalidCrmOrderNumber(order, externalOrderId, id)) {
      _demoOrders.removeWhere(
        (existing) =>
            existing['external_order_id'] == externalOrderId ||
            existing['id'] == id ||
            _isInvalidCrmOrderNumber(
              existing,
              _stringValue(existing['external_order_id']),
              _stringValue(existing['id']),
            ),
      );
      _saveDemoState();
      return;
    }
    final existingIndex = _demoOrders.indexWhere((existing) {
      final existingExternal = _stringValue(existing['external_order_id']);
      final existingId = _stringValue(existing['id']);
      return (externalOrderId.isNotEmpty &&
              existingExternal == externalOrderId) ||
          (id.isNotEmpty && existingId == id);
    });

    final normalized = Map<String, dynamic>.from(order);
    normalized['source'] = _normalizeOrderSource(normalized['source']);
    normalized['id'] = id.isEmpty
        ? DateTime.now().microsecondsSinceEpoch.toString()
        : id;
    normalized['external_order_id'] = externalOrderId.isEmpty
        ? normalized['id']
        : externalOrderId;
    normalized['status'] = _normalizeOrderStatus(normalized['status']);
    normalized['created_at'] ??=
        normalized['scheduled_at'] ?? DateTime.now().toUtc().toIso8601String();
    normalized['assigned_worker_ids'] = List<String>.from(
      (normalized['assigned_worker_ids'] as List?) ?? const [],
    );
    normalized['applications'] = List<Map<String, dynamic>>.from(
      (normalized['applications'] as List?) ?? const [],
    );

    if (existingIndex == -1) {
      _demoOrders.insert(0, normalized);
    } else {
      final existing = _demoOrders[existingIndex];
      final existingStatus = _stringValue(existing['status']);
      final incomingStatus = _stringValue(normalized['status']);
      if (existingStatus.isNotEmpty &&
          existingStatus != 'NEW' &&
          incomingStatus == 'NEW') {
        normalized['status'] = existingStatus;
      }

      final existingAssignedWorkerIds = _assignedWorkerIds(existing);
      final incomingAssignedWorkerIds = _assignedWorkerIds(normalized);
      if (existingAssignedWorkerIds.isNotEmpty &&
          incomingAssignedWorkerIds.isEmpty) {
        normalized['assigned_worker_ids'] = existingAssignedWorkerIds;
      }

      _demoOrders[existingIndex] = {...existing, ...normalized};
    }
    _saveDemoState();
  }

  String _normalizeOrderStatus(dynamic status) {
    switch (status?.toString().toUpperCase()) {
      case 'NEW':
        return 'NEW';
      case 'PROCESSED':
        return 'PROCESSED';
      case 'IN_PROCESS':
        return 'IN_PROCESS';
      case 'DONE_PENDING':
        return 'DONE_PENDING';
      case 'CONVERTED':
        return 'CONVERTED';
      case 'JUNK':
        return 'JUNK';
      default:
        return 'NEW';
    }
  }

  bool _isInvalidCrmOrderNumber(
    Map<String, dynamic> order,
    String externalOrderId,
    String id,
  ) {
    if (order['source'] != sourceCrm) return false;
    final title = _stringValue(order['title']);
    final number = externalOrderId.isNotEmpty
        ? externalOrderId
        : id.isNotEmpty
        ? id
        : title.replaceFirst('Заявка № ', '').trim();
    return !RegExp(r'^\d+/\d{2}$').hasMatch(number);
  }

  bool _isObsoleteDemoCrmOrder(Map<String, dynamic> order) {
    return order['source'] == sourceCrm &&
        order['title'] == 'Разгрузка склада' &&
        order['address'] == 'ул. Складская, 18' &&
        _stringValue(order['external_order_id']).isEmpty;
  }

  bool _isValidCrmOrderNumber(String value) {
    return RegExp(r'^\d+/\d{2}$').hasMatch(value);
  }

  String _crmOrderNumber(Map<String, dynamic> order) {
    final externalOrderId = _stringValue(order['external_order_id']);
    if (_isValidCrmOrderNumber(externalOrderId)) return externalOrderId;

    final id = _stringValue(order['id']);
    if (_isValidCrmOrderNumber(id)) return id;

    final title = _stringValue(order['title']).replaceFirst('Заявка № ', '');
    if (_isValidCrmOrderNumber(title)) return title;

    return externalOrderId.isNotEmpty ? externalOrderId : id;
  }

  Future<Map<String, dynamic>> createDemoCrmOrder() async {
    return createDemoExternalOrder();
  }

  Future<Map<String, dynamic>> createDemoExternalOrder() async {
    final now = DateTime.now();
    const externalOrderId = '14096/26';

    final existingIndex = _demoOrders.indexWhere(
      (order) => order['external_order_id'] == externalOrderId,
    );
    if (existingIndex != -1) {
      return {'success': true, 'orderId': _demoOrders[existingIndex]['id']};
    }

    return createOrder(
      title: 'Разгрузка склада',
      address: 'ул. Складская, 18',
      workersCount: 3,
      hours: 4,
      description:
          'Разгрузить машину, перенести коробки на склад, нужен аккуратный подъем.',
      clientEmail: 'crm@gpm.ru',
      clientPhone: '',
      scheduledAt: now
          .add(const Duration(days: 1, hours: 2))
          .toUtc()
          .toIso8601String(),
      city: 'Москва',
      source: sourceExternal,
      externalOrderId: externalOrderId,
      metro: 'Динамо',
      national: 'yes',
      minTime: 4,
      pricePerHour: 400,
      priceRegular: 450,
      priceState: 450,
      nationality: 'ru',
      workMode: 'shift',
      shiftDescription: 'Дневная смена 09:00-18:00, 5000 руб за смену',
      telegramUsername: 'logist_gpm',
      timezone: 'Europe/Moscow',
      additionalInfo: 'Только РФ',
      addressStreet: 'ул. Складская',
      addressNumber: '18',
      addressLat: 55.7912,
      addressLon: 37.5589,
    );
  }

  Future<Map<String, dynamic>?> getOrderById(String leadId) async {
    final orders = await getOrders();
    try {
      return orders.firstWhere((o) => o['id'] == leadId);
    } catch (_) {
      return null;
    }
  }

  Future<List<Map<String, dynamic>>> getOrdersForWorker(String workerId) async {
    final orders = await getOrders();
    // In API mode the backend derives the worker from the bearer session and
    // already returns worker_application_status/is_assigned_to_worker. Do not
    // overwrite those server-owned fields with the local demo worker id.
    if (isApiMode) return orders;
    return orders.map((order) => _withWorkerMeta(order, workerId)).toList();
  }

  Future<List<Map<String, dynamic>>> getApplicationsForOrder(
    String orderId,
  ) async {
    final orderIndex = _demoOrders.indexWhere(
      (order) => order['id'].toString() == orderId,
    );
    if (orderIndex != -1) {
      final rawApplications = _demoOrders[orderIndex]['applications'];
      if (rawApplications is List && rawApplications.isNotEmpty) {
        return rawApplications
            .whereType<Map>()
            .map(
              (application) => application.map(
                (key, value) => MapEntry(key.toString(), value),
              ),
            )
            .toList();
      }
    }

    return _demoApplications
        .where((application) => application['order_id'] == orderId)
        .map((application) {
          final copy = Map<String, dynamic>.from(application);
          final worker = getWorkerProfileSync(copy['worker_id'].toString());
          if (worker != null) {
            copy['worker'] = worker;
          }
          return copy;
        })
        .toList();
  }

  Map<String, dynamic>? getWorkerProfileSync(String workerId) {
    final worker = _demoWorkers[workerId];
    if (worker == null) return null;

    final copy = Map<String, dynamic>.from(worker);
    copy['priority_group'] = calculatePriorityGroup(copy);
    copy['priority_label'] = priorityGroupLabel(copy['priority_group'] as int);
    return copy;
  }

  Future<Map<String, dynamic>?> getWorkerProfile(String workerId) async {
    return getWorkerProfileSync(workerId);
  }

  Future<bool> updateWorkerProfile(
    String workerId,
    Map<String, dynamic> data,
  ) async {
    final worker = _demoWorkers[workerId];
    if (worker == null) return false;

    worker.addAll(data);
    _saveDemoState();
    return true;
  }

  int calculatePriorityGroup(Map<String, dynamic> worker) {
    if (worker['employment_type'] == 'state') return 1;

    final isRussian = worker['nationality'] == true;
    final hasPassport = (worker['passport']?.toString().isNotEmpty ?? false);
    final hasInn = (worker['inn']?.toString().isNotEmpty ?? false);

    if (isRussian && hasPassport && hasInn) return 2;
    if (isRussian && hasInn) return 3;
    if (hasInn && hasPassport) return 4;
    if (hasInn) return 5;
    if (isRussian && hasPassport) return 6;
    if (hasPassport) return 7;
    if (isRussian) return 8;
    return 0;
  }

  String priorityGroupLabel(int group) {
    switch (group) {
      case 1:
        return 'Штатный';
      case 2:
        return 'РФ, паспорт, самозанятый';
      case 3:
        return 'РФ, самозанятый';
      case 4:
        return 'Паспорт, самозанятый';
      case 5:
        return 'Самозанятый';
      case 6:
        return 'РФ, паспорт';
      case 7:
        return 'Паспорт';
      case 8:
        return 'РФ';
      default:
        return 'Остальные';
    }
  }

  Future<Map<String, dynamic>> applyToOrder({
    required String orderId,
    required String workerId,
    required String workerName,
  }) async {
    if (isApiMode) {
      try {
        final response = await _authenticatedJsonRequest(
          '/app-api/me/orders/${Uri.encodeComponent(orderId)}/applications',
          method: 'POST',
        );
        await _syncAppPublishedOrders();
        return response;
      } catch (error) {
        return {'success': false, 'error': error.toString()};
      }
    }
    final order = await getOrderById(orderId);
    if (order == null) {
      return {'success': false, 'error': 'Заявка не найдена'};
    }

    final existing = _demoApplications.where(
      (application) =>
          application['order_id'] == orderId &&
          application['worker_id'] == workerId,
    );
    if (existing.isNotEmpty) {
      return {'success': true, 'applicationId': existing.first['id']};
    }

    final applicationId = DateTime.now().microsecondsSinceEpoch.toString();
    _demoApplications.insert(0, {
      'id': applicationId,
      'order_id': orderId,
      'worker_id': workerId,
      'worker_name': workerName,
      'status': 'PENDING',
      'created_at': DateTime.now().toUtc().toIso8601String(),
    });
    _saveDemoState();

    return {'success': true, 'applicationId': applicationId};
  }

  Future<Map<String, dynamic>> approveApplication({
    required String orderId,
    required String applicationId,
  }) async {
    if (isApiMode) {
      try {
        final response = await _authenticatedJsonRequest(
          '/app-api/me/orders/${Uri.encodeComponent(orderId)}/applications/'
          '${Uri.encodeComponent(applicationId)}',
          method: 'PATCH',
          body: {'decision': 'APPROVED'},
        );
        await _syncAppPublishedOrders();
        return response;
      } catch (error) {
        return {'success': false, 'error': error.toString()};
      }
    }
    final orderIndex = _demoOrders.indexWhere(
      (order) => order['id'] == orderId,
    );
    if (orderIndex == -1) {
      return {'success': false, 'error': 'Заявка не найдена'};
    }

    final applicationIndex = _demoApplications.indexWhere(
      (application) => application['id'] == applicationId,
    );
    if (applicationIndex == -1) {
      return {'success': false, 'error': 'Отклик не найден'};
    }

    final order = _demoOrders[orderIndex];
    final assignedWorkerIds = _assignedWorkerIds(order);
    final workersCount = order['workers_count'] as int? ?? 1;
    final workerId = _demoApplications[applicationIndex]['worker_id'] as String;

    if (!assignedWorkerIds.contains(workerId) &&
        assignedWorkerIds.length >= workersCount) {
      return {'success': false, 'error': 'Все места уже закрыты'};
    }

    _demoApplications[applicationIndex]['status'] = 'APPROVED';
    if (!assignedWorkerIds.contains(workerId)) {
      assignedWorkerIds.add(workerId);
    }
    order['assigned_worker_ids'] = assignedWorkerIds;
    order['status'] = assignedWorkerIds.length >= workersCount
        ? 'IN_PROCESS'
        : 'PROCESSED';
    _saveDemoState();

    return {'success': true};
  }

  Future<Map<String, dynamic>> rejectApplication(
    String applicationId, {
    String? orderId,
  }) async {
    if (isApiMode) {
      if (orderId == null || orderId.isEmpty) {
        return {'success': false, 'error': 'Не указан заказ'};
      }
      try {
        final response = await _authenticatedJsonRequest(
          '/app-api/me/orders/${Uri.encodeComponent(orderId)}/applications/'
          '${Uri.encodeComponent(applicationId)}',
          method: 'PATCH',
          body: {'decision': 'REJECTED'},
        );
        await _syncAppPublishedOrders();
        return response;
      } catch (error) {
        return {'success': false, 'error': error.toString()};
      }
    }
    final applicationIndex = _demoApplications.indexWhere(
      (application) => application['id'] == applicationId,
    );
    if (applicationIndex == -1) {
      return {'success': false, 'error': 'Отклик не найден'};
    }

    _demoApplications[applicationIndex]['status'] = 'REJECTED';
    _saveDemoState();
    return {'success': true};
  }

  Future<Map<String, dynamic>> closeOrderRecruitment(String orderId) async {
    if (isApiMode) {
      final result = await _patchAppOrder(orderId, {'status': 'IN_PROCESS'});
      if (result['success'] == true) {
        await _syncAppPublishedOrders();
      }
      return result;
    }

    final orderIndex = _demoOrders.indexWhere(
      (order) => order['id'] == orderId,
    );
    if (orderIndex == -1) {
      return {'success': false, 'error': 'Заявка не найдена'};
    }
    final order = _demoOrders[orderIndex];
    final assignedWorkerIds = _assignedWorkerIds(order);
    if (order['status'] != 'PROCESSED') {
      return {'success': false, 'error': 'Поиск уже завершен'};
    }
    if (assignedWorkerIds.isEmpty) {
      return {
        'success': false,
        'error': 'Сначала подтвердите хотя бы одного исполнителя',
      };
    }

    final decidedAt = DateTime.now().toUtc().toIso8601String();
    for (final application in _demoApplications) {
      if (application['order_id'] == orderId &&
          application['status'] == 'PENDING') {
        application['status'] = 'REJECTED';
        application['decided_at'] = decidedAt;
        application['decision_reason'] = 'recruitment_closed';
      }
    }
    order['status'] = 'IN_PROCESS';
    order['recruitment_closed_at'] = decidedAt;
    _saveDemoState();
    return {'success': true, 'order': Map<String, dynamic>.from(order)};
  }

  Future<Map<String, dynamic>> completeOrderWithResult({
    required String orderId,
    required String workerId,
    required String result,
  }) async {
    if (isApiMode) {
      final success = await updateOrderStatus(orderId, 'CONVERTED');
      return success
          ? {'success': true}
          : {'success': false, 'error': 'Не удалось завершить заказ'};
    }
    final orderIndex = _demoOrders.indexWhere(
      (order) => order['id'] == orderId,
    );
    if (orderIndex == -1) {
      return {'success': false, 'error': 'Заявка не найдена'};
    }

    final worker = _demoWorkers[workerId];
    if (worker == null) {
      return {'success': false, 'error': 'Исполнитель не найден'};
    }

    switch (result) {
      case 'success':
        worker['success_requests'] =
            (worker['success_requests'] as int? ?? 0) + 1;
        worker['rating'] = (worker['rating'] as int? ?? 0) + 2;
        break;
      case 'fail':
        worker['fail_requests'] = (worker['fail_requests'] as int? ?? 0) + 1;
        worker['rating'] = (worker['rating'] as int? ?? 0) - 2;
        break;
      case 'good':
        worker['rating'] = (worker['rating'] as int? ?? 0) + 1;
        break;
      case 'neutral':
        break;
      default:
        return {'success': false, 'error': 'Неизвестная оценка'};
    }

    _demoOrders[orderIndex]['status'] = 'CONVERTED';
    _saveDemoState();
    return {'success': true};
  }

  Future<bool> updateOrderStatus(String leadId, String newStatus) async {
    final index = _demoOrders.indexWhere((order) => order['id'] == leadId);
    if (index == -1) return false;

    final order = _demoOrders[index];
    if (hasAppBackend && isApiMode) {
      final externalOrderId = _stringValue(
        order['external_order_id'],
        fallback: leadId,
      );
      final result = await _patchAppOrder(externalOrderId, {
        'status': newStatus,
      });
      if (result['success'] != true && isApiMode) {
        return false;
      }
    }

    _demoOrders[index]['status'] = newStatus;
    _saveDemoState();
    return true;
  }

  Future<Map<String, dynamic>> createContact({
    required String name,
    required String email,
    required String phone,
    required String role,
  }) async {
    return {
      'success': true,
      'contactId': DateTime.now().millisecondsSinceEpoch.toString(),
    };
  }

  Future<List<Map<String, dynamic>>> getContacts() async {
    return [];
  }

  Future<bool> addComment(String leadId, String comment) async {
    return true;
  }

  Future<Map<String, dynamic>> createDeal({
    required String title,
    required int amount,
    required String contactId,
  }) async {
    return {'success': true, 'dealId': '1'};
  }

  Future<Map<String, dynamic>> getFinancialStats() async {
    return {'totalIncome': 125000, 'totalDeals': 47, 'averageDeal': 2659};
  }

  Map<String, dynamic> _mapValue(dynamic value) {
    if (value is Map<String, dynamic>) return value;
    if (value is Map) {
      return value.map((key, item) => MapEntry(key.toString(), item));
    }
    if (value is String && value.trim().isNotEmpty) {
      try {
        final decoded = jsonDecode(value);
        if (decoded is Map<String, dynamic>) return decoded;
        if (decoded is Map) {
          return decoded.map((key, item) => MapEntry(key.toString(), item));
        }
      } catch (_) {
        return <String, dynamic>{};
      }
    }
    return <String, dynamic>{};
  }

  String _stringValue(dynamic value, {String fallback = ''}) {
    final text = value?.toString().trim() ?? '';
    return text.isEmpty ? fallback : text;
  }

  int _intValue(dynamic value, {required int fallback}) {
    return _intOrNull(value) ?? fallback;
  }

  int? _intOrNull(dynamic value) {
    if (value is int) return value;
    if (value is num) return value.round();
    return int.tryParse(value?.toString().trim() ?? '');
  }

  double? _doubleOrNull(dynamic value) {
    if (value is double) return value;
    if (value is num) return value.toDouble();
    return double.tryParse(value?.toString().trim() ?? '');
  }

  String _nationalFromOrderData(dynamic value, String additionalInfo) {
    final normalizedValue = value?.toString().trim().toLowerCase();
    if (value == true ||
        {'yes', 'ru', 'rf', 'russian'}.contains(normalizedValue)) {
      return 'yes';
    }
    if (value == false ||
        {'no', 'non_ru', 'non-rf', 'foreign'}.contains(normalizedValue)) {
      return 'no';
    }
    final normalized = additionalInfo.toLowerCase();
    if (normalized.contains('только не рф') ||
        normalized.contains('non-rf only')) {
      return 'no';
    }
    if (normalized.contains('только рф') ||
        normalized.contains('rf only') ||
        normalized.contains('russian only')) {
      return 'yes';
    }
    return 'every';
  }

  Map<String, dynamic> _withWorkerMeta(
    Map<String, dynamic> order,
    String workerId,
  ) {
    final copy = Map<String, dynamic>.from(order);
    final assignedWorkerIds = _assignedWorkerIds(copy);
    final workerApplications = _demoApplications.where(
      (application) =>
          application['order_id'] == copy['id'] &&
          application['worker_id'] == workerId,
    );
    final applications = _demoApplications.where(
      (application) => application['order_id'] == copy['id'],
    );

    copy['assigned_worker_ids'] = assignedWorkerIds;
    copy['assigned_count'] = assignedWorkerIds.length;
    copy['applications_count'] = applications.length;
    copy['worker_application_status'] = workerApplications.isEmpty
        ? null
        : workerApplications.first['status'];
    copy['is_assigned_to_worker'] = assignedWorkerIds.contains(workerId);
    return copy;
  }

  List<String> _assignedWorkerIds(Map<String, dynamic> order) {
    final rawIds = order['assigned_worker_ids'];
    if (rawIds is List<String>) return List<String>.from(rawIds);
    if (rawIds is List) return rawIds.map((id) => id.toString()).toList();
    return <String>[];
  }

  void _loadDemoState() {
    final rawState = readDemoValue('gpm_demo_state_v1');
    if (rawState == null || rawState.isEmpty) return;

    try {
      final decoded = jsonDecode(rawState);
      if (decoded is! Map<String, dynamic>) return;

      final orders = decoded['orders'];
      if (orders is List) {
        _demoOrders
          ..clear()
          ..addAll(
            orders.map((order) {
              final copy = Map<String, dynamic>.from(order);
              if (copy['source'] == 'crm' &&
                  copy['title'] == 'Разгрузка из CRM') {
                copy['title'] = 'Разгрузка склада';
              }
              final description = copy['description']?.toString();
              if (copy['source'] == 'crm' &&
                  description != null &&
                  description.startsWith('CRM: ')) {
                copy['description'] = description.substring(5);
              }
              return copy;
            }),
          );
      }

      final applications = decoded['applications'];
      if (applications is List) {
        _demoApplications
          ..clear()
          ..addAll(
            applications.map(
              (application) => Map<String, dynamic>.from(application),
            ),
          );
      }

      final workers = decoded['workers'];
      if (workers is Map) {
        _demoWorkers
          ..clear()
          ..addAll(
            workers.map(
              (key, value) => MapEntry(
                key.toString(),
                Map<String, dynamic>.from(value as Map),
              ),
            ),
          );
      }
      _normalizeDemoCrmOrders();
      _saveDemoState();
    } catch (_) {
      // If demo state is malformed, keep bundled seed data.
    }
  }

  void _normalizeDemoCrmOrders() {
    final seenDemoCrmOrderIds = <String>{};
    final normalizedOrders = <Map<String, dynamic>>[];

    for (final order in _demoOrders) {
      final copy = Map<String, dynamic>.from(order);
      final isCrm = copy['source'] == 'crm';
      final externalOrderId = _stringValue(copy['external_order_id']);
      final id = _stringValue(copy['id']);

      if (_isInvalidCrmOrderNumber(copy, externalOrderId, id) &&
          !_isObsoleteDemoCrmOrder(copy)) {
        continue;
      }

      if (isCrm && copy['title'] == 'Разгрузка из CRM') {
        copy['title'] = 'Разгрузка склада';
      }

      final description = copy['description']?.toString();
      if (isCrm && description != null && description.startsWith('CRM: ')) {
        copy['description'] = description.substring(5);
      }

      if (isCrm &&
          copy['title'] == 'Разгрузка склада' &&
          copy['address'] == 'ул. Складская, 18') {
        copy['id'] = '14096/26';
        copy['external_order_id'] = '14096/26';
        copy['title'] = 'Заявка № 14096/26';
      }

      final normalizedExternalOrderId = _crmOrderNumber(copy);
      if (isCrm && normalizedExternalOrderId.isNotEmpty) {
        if (!_isValidCrmOrderNumber(normalizedExternalOrderId)) {
          continue;
        }
        copy['id'] = normalizedExternalOrderId;
        copy['external_order_id'] = normalizedExternalOrderId;
        copy['title'] = 'Заявка № $normalizedExternalOrderId';
        if (seenDemoCrmOrderIds.contains(normalizedExternalOrderId)) {
          continue;
        }
        seenDemoCrmOrderIds.add(normalizedExternalOrderId);
      }

      if (isCrm) {
        copy['source'] = sourceExternal;
      }

      normalizedOrders.add(copy);
    }

    _demoOrders
      ..clear()
      ..addAll(normalizedOrders);
  }

  void _saveDemoState() {
    if (!usesLocalPersistence) return;

    writeDemoValue(
      'gpm_demo_state_v1',
      jsonEncode({
        'orders': _demoOrders,
        'applications': _demoApplications,
        'workers': _demoWorkers,
      }),
    );
  }
}
