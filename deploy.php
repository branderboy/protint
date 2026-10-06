<?php
/**
 * GitHub webhook deploy endpoint for HostGator.
 *
 * Flow:
 *   1. GitHub App sends a `push` webhook to https://<domain>/deploy.php
 *   2. We verify the X-Hub-Signature-256 HMAC against DEPLOY_WEBHOOK_SECRET
 *   3. If the push is on the configured branch, we download the repo zip
 *      from the GitHub API using DEPLOY_GITHUB_TOKEN
 *   4. Extract into a staging dir, then sync into DEPLOY_TARGET_DIR
 *
 * Secrets live in deploy-config.php (gitignored). See deploy-config.example.php.
 */

declare(strict_types=1);

set_time_limit(0);
ignore_user_abort(true);

// ---- Bootstrap ---------------------------------------------------------

$configFile = __DIR__ . '/deploy-config.php';
if (!is_file($configFile)) {
    http_response_code(500);
    exit("deploy-config.php not found");
}
$config = require $configFile;

$logFile = $config['log_file'] ?? __DIR__ . '/deploy.log';
$log = function (string $msg) use ($logFile): void {
    @file_put_contents(
        $logFile,
        '[' . gmdate('c') . '] ' . $msg . PHP_EOL,
        FILE_APPEND | LOCK_EX
    );
};

// ---- Verify request ----------------------------------------------------

// Manual re-deploy: GET /deploy.php?manual=1&token=<manual_token from config>
// Deploys the tip of the configured branch. Use after fixing config (e.g. a
// renewed GitHub token) without waiting for the next push webhook.
if (($_SERVER['REQUEST_METHOD'] ?? '') === 'GET' && isset($_GET['manual'])) {
    $manualToken = (string)($config['manual_token'] ?? $config['webhook_secret']);
    if (!hash_equals($manualToken, (string)($_GET['token'] ?? ''))) {
        $log('manual deploy rejected: bad token');
        http_response_code(401);
        exit('bad token');
    }
    $log('manual deploy requested');
    runDeploy('refs/heads/' . $config['branch'], $config, $log);
    exit;
}

if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
    http_response_code(405);
    exit('method not allowed');
}

$payload = file_get_contents('php://input') ?: '';
$signature = $_SERVER['HTTP_X_HUB_SIGNATURE_256'] ?? '';
$expected = 'sha256=' . hash_hmac('sha256', $payload, $config['webhook_secret']);

if (!hash_equals($expected, $signature)) {
    $log('rejected: signature mismatch');
    http_response_code(401);
    exit('bad signature');
}

$event = $_SERVER['HTTP_X_GITHUB_EVENT'] ?? '';
if ($event === 'ping') {
    $log('ping ok');
    echo 'pong';
    exit;
}
if ($event !== 'push') {
    $log("ignored event: $event");
    echo "ignored: $event";
    exit;
}

$body = json_decode($payload, true);
if (!is_array($body)) {
    http_response_code(400);
    exit('invalid json');
}

$ref = $body['ref'] ?? '';
$expectedRef = 'refs/heads/' . $config['branch'];
if ($ref !== $expectedRef) {
    $log("ignored ref: $ref");
    echo "ignored ref: $ref";
    exit;
}

$commit = $body['after'] ?? $config['branch'];
runDeploy($commit, $config, $log);

// ---- Helpers -----------------------------------------------------------

function runDeploy(string $commit, array $config, callable $log): void {
    $logFile = $config['log_file'] ?? __DIR__ . '/deploy.log';
    $log("deploy start: $commit");

    // ---- Download archive ----------------------------------------------

    $archiveUrl = sprintf(
        'https://api.github.com/repos/%s/%s/zipball/%s',
        rawurlencode($config['owner']),
        rawurlencode($config['repo']),
        rawurlencode($commit)
    );

    $tmpZip = tempnam(sys_get_temp_dir(), 'ghdeploy_') . '.zip';
    $fh = fopen($tmpZip, 'wb');

    $ch = curl_init($archiveUrl);
    curl_setopt_array($ch, [
        CURLOPT_FILE => $fh,
        CURLOPT_FOLLOWLOCATION => true,
        CURLOPT_HTTPHEADER => [
            'Authorization: Bearer ' . $config['github_token'],
            'Accept: application/vnd.github+json',
            'X-GitHub-Api-Version: 2022-11-28',
            'User-Agent: hostgator-deploy-php',
        ],
        CURLOPT_CONNECTTIMEOUT => 30,
        CURLOPT_TIMEOUT => 600,
        // Abort only if the transfer stalls below 1 KB/s for 60s, rather
        // than a hard wall-clock cap on the whole download.
        CURLOPT_LOW_SPEED_LIMIT => 1024,
        CURLOPT_LOW_SPEED_TIME => 60,
    ]);
    $ok = curl_exec($ch);
    $status = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    $err = curl_error($ch);
    curl_close($ch);
    fclose($fh);

    if (!$ok || $status >= 400) {
        @unlink($tmpZip);
        // A 401/403/404 here almost always means the github_token in
        // deploy-config.php is expired or lacks access to the repo.
        $hint = in_array($status, [401, 403, 404], true)
            ? ' (check github_token in deploy-config.php - expired or no repo access?)'
            : '';
        $log("download failed: status=$status err=$err$hint");
        http_response_code(502);
        exit("download failed: HTTP $status $err$hint");
    }
    $log('downloaded ' . number_format((float)filesize($tmpZip)) . ' bytes');

    // ---- Extract --------------------------------------------------------

    $stageDir = sys_get_temp_dir() . '/ghdeploy_' . bin2hex(random_bytes(6));
    if (!mkdir($stageDir, 0755, true)) {
        @unlink($tmpZip);
        $log('stage mkdir failed');
        http_response_code(500);
        exit('stage failed');
    }

    $zip = new ZipArchive();
    if ($zip->open($tmpZip) !== true) {
        @unlink($tmpZip);
        $log('zip open failed');
        http_response_code(500);
        exit('zip open failed');
    }
    $zip->extractTo($stageDir);
    $zip->close();
    @unlink($tmpZip);

    // GitHub zip wraps everything in a single top-level dir like owner-repo-sha/
    $entries = array_values(array_diff(scandir($stageDir), ['.', '..']));
    if (count($entries) !== 1 || !is_dir($stageDir . '/' . $entries[0])) {
        rrmdir($stageDir);
        $log('unexpected zip layout');
        http_response_code(500);
        exit('bad zip layout');
    }
    $sourceDir = $stageDir . '/' . $entries[0];

    // ---- Sync into target ------------------------------------------------

    $targetDir = rtrim($config['target_dir'], '/');
    if (!is_dir($targetDir)) {
        rrmdir($stageDir);
        $log("target missing: $targetDir");
        http_response_code(500);
        exit('target missing');
    }

    $free = @disk_free_space($targetDir);
    if ($free !== false) {
        $log('disk free: ' . number_format($free) . ' bytes');
    }

    $preserve = array_merge(
        ['deploy.php', 'deploy-config.php', basename($logFile)],
        $config['preserve'] ?? []
    );

    try {
        syncDir($sourceDir, $targetDir, $preserve);
        $log("deploy ok: $commit");
        echo "deployed $commit";
    } catch (Throwable $e) {
        $log('sync error: ' . $e->getMessage());
        http_response_code(500);
        echo 'sync error: ' . $e->getMessage();
    } finally {
        rrmdir($stageDir);
    }
}

function syncDir(string $src, string $dst, array $preserve): void {
    if (!is_dir($dst) && !mkdir($dst, 0755, true)) {
        throw new RuntimeException("mkdir $dst failed");
    }

    foreach (scandir($src) as $entry) {
        if ($entry === '.' || $entry === '..') continue;
        $from = $src . '/' . $entry;
        $to = $dst . '/' . $entry;
        if (is_dir($from)) {
            syncDir($from, $to, []);
        } else {
            if (!copy($from, $to)) {
                throw new RuntimeException("copy $to failed");
            }
        }
    }

    foreach (scandir($dst) as $entry) {
        if ($entry === '.' || $entry === '..') continue;
        if (in_array($entry, $preserve, true)) continue;
        if (file_exists($src . '/' . $entry)) continue;
        $path = $dst . '/' . $entry;
        is_dir($path) ? rrmdir($path) : @unlink($path);
    }
}

function rrmdir(string $dir): void {
    if (!is_dir($dir)) return;
    foreach (scandir($dir) as $entry) {
        if ($entry === '.' || $entry === '..') continue;
        $path = $dir . '/' . $entry;
        is_dir($path) ? rrmdir($path) : @unlink($path);
    }
    @rmdir($dir);
}
