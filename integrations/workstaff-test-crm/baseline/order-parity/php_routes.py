"""Find active PHP route declarations without activating commented-out code."""
import re
import shutil
import subprocess
from pathlib import Path

ROUTE = re.compile(r'Route::(?:get|post|put|patch|delete|resource|apiResource|match|any)\s*\([^;]*;')
MASK = r'''
$source = stream_get_contents(STDIN);
foreach (token_get_all($source) as $token) {
    if (!is_array($token)) { echo $token; continue; }
    echo in_array($token[0], [T_COMMENT, T_DOC_COMMENT], true)
        ? preg_replace('/[^\r\n]/u', ' ', $token[1]) : $token[1];
}
'''


def active_routes(text, php=None):
    php = php or ('/opt/php74/bin/php' if Path('/opt/php74/bin/php').is_file() else shutil.which('php'))
    if not php:
        raise RuntimeError('PHP_ROUTE_TOKENIZER_REQUIRED')
    result = subprocess.run([php, '-r', MASK], input=text.encode('utf-8'), capture_output=True)
    if result.returncode:
        raise RuntimeError('PHP_ROUTE_TOKENIZATION_FAILED')
    masked = result.stdout.decode('utf-8')
    if len(masked) != len(text) or masked.count('\n') != text.count('\n'):
        raise RuntimeError('PHP_ROUTE_SOURCE_OFFSETS_CHANGED')
    return ROUTE.finditer(masked)


def route_prefix(statement):
    match = re.search(r'\(\s*[\'\"]/?([^\'\"/]+)', statement)
    return match.group(1) if match else None
