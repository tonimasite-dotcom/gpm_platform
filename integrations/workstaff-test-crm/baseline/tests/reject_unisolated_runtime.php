<?php
// Run outside unshare --net: it must reject BEFORE loading the application.
try {
    require __DIR__ . '/../payload/private_runtime_bootstrap.php';
} catch (RuntimeException $error) {
    if ($error->getMessage() === 'PRIVATE_RUNTIME_CONTEXT_REQUIRED') {
        echo "Unisolated runtime refused before application bootstrap\n";
        exit(0);
    }
}
fwrite(STDERR, "Expected private runtime refusal did not occur\n");
exit(1);
