"""Safety regression: disabled upstream routes must remain disabled."""
import unittest
from php_routes import active_routes, route_prefix


class ActiveRouteTests(unittest.TestCase):
    def test_leading_slash_keeps_static_route_in_the_same_prefix(self):
        self.assertEqual(route_prefix("Route::get('/loaders/map', [C::class, 'map']);"), 'loaders')
        self.assertEqual(route_prefix("Route::resource('loaders', C::class);"), 'loaders')

    def test_disabled_routes_and_unicode_comments_keep_source_offsets(self):
        text = """<?php
// Отключенный маршрут не переносится.
// Route::post('disabled', [Controller::class, 'store']);
/* Route::delete('also_disabled', [Controller::class, 'delete']); */
Route::get('enabled', [Controller::class, 'index']);
"""
        matches = list(active_routes(text))
        self.assertEqual(len(matches), 1)
        self.assertEqual(text[matches[0].start():matches[0].end()],
                         "Route::get('enabled', [Controller::class, 'index']);")

    def test_comment_syntax_inside_route_arguments_remains_literal(self):
        text = "<?php Route::get('https://example.invalid/*literal*/', [C::class, 'index']);"
        self.assertEqual([m.group(0) for m in active_routes(text)], [text[6:]])

    def test_inline_comments_do_not_hide_active_routes(self):
        text = "<?php Route::post(/* пояснение */ 'enabled', [C::class, 'store']);"
        matches = list(active_routes(text))
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].start(), 6)
        self.assertEqual(matches[0].end(), len(text))


if __name__ == '__main__':
    unittest.main()
