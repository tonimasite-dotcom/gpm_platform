import 'package:gpm_platform/registration/registration_preview_api.dart';

const previewLocations = <Map<String, dynamic>>[
  {'id': 101, 'kind': 'city', 'name': 'Москва', 'enabled': true},
  {'id': 102, 'kind': 'city', 'name': 'Санкт-Петербург', 'enabled': true},
  {'id': 501, 'kind': 'district', 'city_id': 101, 'name': 'Северный округ', 'enabled': true},
  {'id': 502, 'kind': 'district', 'city_id': 102, 'name': 'Центральный район', 'enabled': true},
];

Map<String, dynamic> previewAnswers() => {
  'phone': '+70000000000', 'phone_country': 'RU', 'city_ids': [101], 'district_ids': [502],
  'first_name': 'Иван', 'last_name': 'Иванов', 'middle_name': 'Иванович', 'birth_date': '1994-01-01',
  'citizenship_ru': false, 'has_straps': false, 'has_tools': false,
};

class FakeRegistrationGateway implements RegistrationPreviewGateway {
  Map<String, dynamic> state;
  int loads = 0;
  int completions = 0;
  String? rejectedField;
  FakeRegistrationGateway({String step = 'phone', bool completed = false}) : state = {
    'preview': true, 'registration_id': 'reg_synthetic', 'revision': 0,
    'current_step': step, 'status': completed ? 'completed' : step == 'review' ? 'review' : 'draft',
    'answers': step == 'phone' ? <String, dynamic>{} : previewAnswers(),
    'phone_verified': step != 'phone', 'challenge_active': false,
    'middle_name_required': false, 'profile_active': false,
    if (completed) 'profile_id': 'preview_synthetic',
  };

  Map<String, dynamic> result() => {...state, 'answers': Map<String, dynamic>.from(state['answers'] as Map)};
  @override
  Future<Map<String, dynamic>> load() async { loads++; return result(); }
  @override
  Future<List<Map<String, dynamic>>> locations() async => previewLocations;
  @override
  Future<Map<String, dynamic>> save(Map<String, dynamic> values) async {
    if (rejectedField != null) throw RegistrationPreviewError('INVALID_NAME', 'Используй буквы и дефис, без пробелов и цифр', rejectedField);
    final answers = Map<String, dynamic>.from(state['answers'] as Map);
    if (values.containsKey('phone') && values['phone'] != answers['phone']) {
      state['phone_verified'] = false;
      state['challenge_active'] = false;
    }
    answers.addAll(values);
    state['answers'] = answers;
    state['revision'] = (state['revision'] as int) + 1;
    return result();
  }
  @override
  Future<Map<String, dynamic>> challenge() async {
    state['challenge_active'] = true; state['test_code'] = '123456';
    return result();
  }
  @override
  Future<Map<String, dynamic>> verify(String code) async {
    if (code != '123456') throw const RegistrationPreviewError('INVALID_CODE', 'Неверный код. Попробуй еще раз', 'code');
    state['phone_verified'] = true; state['revision'] = (state['revision'] as int) + 1;
    return result();
  }
  @override
  Future<Map<String, dynamic>> complete() async {
    completions++;
    state['status'] = 'completed'; state['profile_id'] = 'preview_synthetic';
    return result();
  }
  @override
  Future<Map<String, dynamic>> restart() async {
    state = FakeRegistrationGateway().state;
    return result();
  }
  @override
  Future<Map<String, dynamic>> newSession() => restart();
}
