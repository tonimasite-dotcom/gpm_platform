# Font fixtures for mobile layout tests

Roboto Regular, Bold and Black from the Flutter SDK material font bundle.
The Apache 2.0 license supplied with that bundle is preserved in `LICENSE.txt`.

These files are used only by widget tests, under the app's Arial family name,
to exercise real mobile font metrics rather than Ahem's square glyphs. They
are not registered in pubspec.yaml and are not included in production assets.
Keeping them here makes tests independent of the host OS and SDK font cache.
