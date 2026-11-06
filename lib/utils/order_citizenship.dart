/// Orders either require Russian citizenship or accept any citizenship.
/// Legacy no/non_ru values mean that Russian citizenship is not required.
bool orderRequiresRussianCitizenship(Map<String, dynamic> order) {
  final value = order['national'] ?? order['nationality'];
  return value == true ||
      {
        'yes',
        'ru',
        'rf',
        'russian',
      }.contains(value?.toString().trim().toLowerCase());
}

String orderCitizenshipText(Map<String, dynamic> order) =>
    orderRequiresRussianCitizenship(order) ? 'Только РФ' : 'Любое';
