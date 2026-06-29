import 'package:web/web.dart' as web;

String? readDemoValue(String key) => web.window.localStorage.getItem(key);

void writeDemoValue(String key, String value) {
  web.window.localStorage.setItem(key, value);
}
