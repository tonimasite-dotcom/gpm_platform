<?php
// Static inventory only. String literals/comments never enter the report.
if (PHP_SAPI !== 'cli') { exit(2); }
$root = realpath($argv[1] ?? '');
$allowed = '/root/gpm-ts-update/20261106-baseline-01/';
if (!$root || strpos($root . '/', $allowed) !== 0 || !is_dir($root . '/app')) { exit(2); }
$rows = [];
foreach (new RecursiveIteratorIterator(new RecursiveDirectoryIterator($root . '/app', FilesystemIterator::SKIP_DOTS)) as $file) {
    if (!$file->isFile() || $file->isLink() || $file->getExtension() !== 'php') { continue; }
    $source = file_get_contents($file->getPathname());
    $tokens = token_get_all($source);
    $method = '(file)'; $pending = false; $hits = [];
    foreach ($tokens as $index => $token) {
        if (!is_array($token)) { if ($token === '(') { $pending = false; } continue; }
        if ($token[0] === T_FUNCTION) { $pending = true; continue; }
        if ($pending && $token[0] === T_STRING) { $method = $token[1]; $pending = false; }
        if ($token[0] !== T_STRING) { continue; }
        $next = $index + 1;
        while (isset($tokens[$next]) && is_array($tokens[$next]) && in_array($tokens[$next][0], [T_WHITESPACE, T_COMMENT, T_DOC_COMMENT], true)) { ++$next; }
        $following = $tokens[$next] ?? null;
        if ($following !== '(' && !(is_array($following) && $following[0] === T_DOUBLE_COLON)) { continue; }
        if (in_array(strtolower($token[1]), ['curl_exec', 'curl_multi_exec', 'fsockopen', 'pfsockopen', 'stream_socket_client', 'mail', 'http', 'client', 'swift_mailer', 'swift_smtptransport', 'connect', 'request', 'requestasync', 'sendasync', 'getasync', 'postasync', 'file_get_contents', 'fopen', 'soapclient', 'shell_exec', 'exec', 'system', 'popen', 'proc_open', 'yageo', 'socialite', 'broadcast', 'verifyresponse'], true)) {
            $hits[] = ['line' => $token[2], 'method' => $method, 'symbol' => $token[1]];
        }
    }
    if ($hits) { $rows[] = ['file' => substr($file->getPathname(), strlen($root) + 1), 'sha256' => hash('sha256', $source), 'hits' => $hits]; }
}
echo json_encode(['source' => basename($root), 'application_bootstrapped' => false, 'files' => $rows], JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES) . "\n";
