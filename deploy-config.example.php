<?php
/**
 * Copy this file to deploy-config.php on the HostGator server and fill in
 * real values. deploy-config.php is gitignored so secrets never reach the
 * repo. chmod 600 the live file.
 */

return [
    // Repo to pull from.
    'owner'  => 'branderboy',
    'repo'   => 'protint',
    'branch' => 'main',

    // Webhook secret configured on the GitHub App / repo webhook.
    'webhook_secret' => 'change-me-to-a-long-random-string',

    // Installation access token from the GitHub App, or a fine-grained PAT
    // with Contents: Read on this repo. Installation tokens expire hourly,
    // so prefer a small helper that refreshes them, or use a fine-grained
    // PAT for simplicity on shared hosting.
    'github_token' => 'ghs_xxx_or_github_pat_xxx',

    // Absolute path on HostGator where the site should live.
    // e.g. /home/<cpaneluser>/public_html
    'target_dir' => '/home/CPANELUSER/public_html',

    // Files/dirs in target_dir that should never be overwritten or deleted
    // by a deploy (deploy.php, deploy-config.php, and the log file are
    // always preserved automatically).
    'preserve' => [
        '.htaccess',
        'cgi-bin',
    ],

    // Deploy log location. Keep it outside the docroot if you can; if it
    // must stay inside, deny it via .htaccess.
    'log_file' => __DIR__ . '/deploy.log',
];
