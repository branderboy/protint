# URL submission (IndexNow + Bing)

Tells search engines when pages on this site are new or updated, so they
get crawled sooner. Free services only.

| Target | What it reaches | When it runs |
| --- | --- | --- |
| IndexNow | Bing, Yandex, Seznam, Naver | Always |
| Bing Webmaster API | Bing | Only if the `BING_WEBMASTER_API_KEY` secret exists |

Google is not included. Google does not support IndexNow, and its
Indexing API is only for job postings and livestreams. Google finds
updates through the sitemap.

## How it works

1. Reads the live sitemap (the `Sitemap:` line in `robots.txt`). Sitemap
   index files and nested sitemaps are followed.
2. Picks the URLs to send: new URLs, URLs whose `lastmod` changed, and,
   after a push, pages whose `.html` file changed in that push. That last
   rule matters because the sitemap `lastmod` dates are edited by hand
   and often go stale.
3. Checks each URL first. Anything that is not a 200 (including
   redirects) or carries a `noindex` tag or header is skipped and logged.
4. Submits, then records the result per URL and per target.

The IndexNow key is the `<32 hex characters>.txt` file at the repo root.
It deploys with the site and is served at `https://<site>/<key>.txt`. It
is meant to be public. Do not rename or delete it.

## When it runs (GitHub Actions)

`.github/workflows/indexing.yml` runs:

- after every push to `main`. `deploy.php` does not report back to
  GitHub, so the workflow waits until a file from the push is served
  live (up to 10 minutes) before reading the sitemap.
- daily at 10:37 UTC.
- by hand: Actions tab > "Submit URLs for indexing" > Run workflow. You
  can pick the target, a dry run, or force (resubmit everything).

## Where the state and log live

The workflow commits `submitted.json` and `log.csv` to the
`indexing-state` branch, not `main`. `deploy.php` only deploys `main`, so
these files never reach the website and saving them never redeploys the
site. It was chosen over the Actions cache because the cache expires and
cannot be browsed.

- `submitted.json`: every URL, its `lastmod`, and per target the last
  submission time, response code, and whether it succeeded. Failed URLs
  are retried on the next run.
- `log.csv`: one row per run and target, plus one row per skipped URL.

### Reading log.csv

| Column | Meaning |
| --- | --- |
| `timestamp` | UTC time of the row |
| `target` | `indexnow`, `bing`, or `check` (a URL skipped before submitting) |
| `url_count` | URLs in that request |
| `status_code` | `200`/`202` = accepted, `nothing-to-do`, `skipped`, or an error code |
| `error` | Why it failed, or which URL was skipped and why |

IndexNow codes: `200`/`202` accepted, `400` bad request, `403` key not
valid (key file missing or not live yet), `422` URL does not belong to
this host, `429` too many requests.

## Secrets (repo Settings > Secrets and variables > Actions)

| Secret | Needed for | Where to get it |
| --- | --- | --- |
| `BING_WEBMASTER_API_KEY` | Bing API (optional) | Bing Webmaster Tools > Settings > API access. The site must be verified there first. |

IndexNow needs no secret. Optional variable for the Bing module:
`BING_SITE_URL`, only if the site is registered in Bing under a URL other
than `https://www.<domain>/`.

Never commit an API key. The IndexNow key file is the only key in the repo.

## Run it locally

Python 3.9 or newer, no packages to install. From the repo root:

```sh
python3 indexing/submit.py --dry-run            # show what would be sent
python3 indexing/submit.py                      # submit (IndexNow, plus Bing if the key is set)
python3 indexing/submit.py --target indexnow --limit 5
python3 indexing/submit.py --urls my-list.txt   # submit only these URLs (one per line)
python3 indexing/submit.py --force              # resubmit everything
BING_WEBMASTER_API_KEY=xxxx python3 indexing/submit.py --target bing
```

Local runs keep their state in `.indexing/` (gitignored), separate from
the workflow's `indexing-state` branch. To use the workflow's state,
check that branch out and pass `--state-dir <folder>`.
