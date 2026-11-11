import unittest
from complete_migration_dependencies import references


class ClassDependencyTests(unittest.TestCase):
    def test_same_namespace_static_helper_is_included(self):
        source = '<?php\nnamespace App\\Services\\Document;\nPaymentReference::parse($value);'
        self.assertIn('App\\Services\\Document\\PaymentReference', references(source))

    def test_grouped_import_and_alias_are_resolved(self):
        source = '<?php\nnamespace App\\Example;\nuse App\\Other\\{One, Two as Alias};\nAlias::read();'
        result = references(source)
        self.assertIn('App\\Other\\One', result)
        self.assertIn('App\\Other\\Two', result)
        self.assertNotIn('App\\Example\\Alias', result)

    def test_imported_facade_does_not_become_a_local_class(self):
        source = '<?php\nnamespace App\\Example;\nuse Illuminate\\Support\\Facades\\DB;\nDB::table("orders");'
        self.assertNotIn('App\\Example\\DB', references(source))

    def test_same_namespace_constructor_parameter_and_return_type(self):
        source = '<?php\nnamespace App\\Example;\nfunction make(Input $value): Output { return new Output; }'
        result = references(source)
        self.assertIn('App\\Example\\Input', result)
        self.assertIn('App\\Example\\Output', result)


if __name__ == '__main__':
    unittest.main()
