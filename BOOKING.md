# Booking: Do Not Break

Customers book tinting through Acuity. If a booking link breaks, the
shop loses appointments and nobody notices until a customer calls. Read
this before touching `book.html`, any `locations/*.html` page, the
`#book` sections, or the `.acuity-embed-wrap` CSS.

Last full check: 2026-10-21 (repo links, anchors and live `book.html`
all match the table below).

## The booking links (source of truth)

Acuity owner: `14099514`. Base URL:
`https://app.acuityscheduling.com/schedule.php?owner=14099514&appointmentType=category:Window+Tinting&calendarID=<ID>`

| Shop | calendarID | Where it is used |
| --- | --- | --- |
| Capitol Heights | `2200795` | `book.html` card, `locations/capitol-heights.html` (hero Book Online button, iframe, fallback link, 2 text links in the body) |
| Bowie | `1838105` | `book.html` card, `locations/bowie.html` (hero Book Online button, iframe, fallback link, 2 text links in the body) |
| Clinton | `10104513` | `book.html` card, `locations/clinton.html` (hero Book Online button, iframe, fallback link, 2 text links in the body) |
| Upper Marlboro | `10132290` | `book.html` card, `locations/upper-marlboro.html` (hero Book Online button, iframe, fallback link, 2 text links in the body) |

Each shop link appears exactly 6 times in the repo (1 on `book.html`,
5 on its location page). Keep the
`appointmentType=category:Window+Tinting` filter on every link, or the
customer sees Pro Wash detailing services.

Do not confuse these with the Pro Wash calendars (`1406436`, `1424862`,
`1838107`, `10171213`), which have no tinting service. Bowie is the
trap: Pro Tint Bowie is `1838105`, Pro Wash Bowie is `1838107`. One
digit off books the customer into the wrong business.

## Rules

1. One booking per shop. Never one shared calendar, never a location
   picker on our page (customers ended up picking a location twice).
2. `book.html`: one card per shop. The red button opens that shop's own
   Acuity link in a new tab (`target="_blank" rel="noopener"`). A plain
   text link under it goes to the shop page.
3. Each location page has a section with `id="book"` holding that
   shop's iframe plus the "Calendar not loading?" fallback link. The
   page's non-hero Book Online buttons jump to `#book`. Do not rename or
   remove `id="book"`.
4. Keep the `embed.js` script after each iframe
   (`https://embed.acuityscheduling.com/js/embed.js`). It sizes the
   iframe.
5. Never change a calendarID from memory or by copying from another
   page. Only change it after checking the shop's link in Acuity
   (Acuity > Business Settings > Scheduling Page > Direct links), then
   update this table and CLAUDE.md in the same commit.
6. Do not add `sandbox`, a Content-Security-Policy, or an
   `X-Frame-Options` rule that blocks `app.acuityscheduling.com` or
   `embed.acuityscheduling.com`.
7. There is no DC shop. Never add a DC booking link.

## Check before every push that touches booking

Run from the repo root:

```sh
# Every shop link should print 6
for id in 2200795 1838105 10104513 10132290; do
  printf '%s ' "$id"; grep -rho "category:Window+Tinting&calendarID=$id\"" --include=*.html . | wc -l
done

# No Pro Wash calendar and no unfiltered link
grep -rnE 'calendarID=(1406436|1424862|1838107|10171213)' --include=*.html .
grep -rn 'owner=14099514&calendarID' --include=*.html .

# Every location page still has its booking section
grep -c 'id="book"' locations/capitol-heights.html locations/bowie.html locations/clinton.html locations/upper-marlboro.html
```

The two `grep -rn` lines must print nothing. Then, after the deploy,
open `https://www.protintdmv.com/book.html`, tap each shop button, and
confirm the Acuity page shows that shop's name and the tinting
services. Open each location page and confirm the calendar loads.
