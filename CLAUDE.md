# Pro Tint DMV (protintdmv.com)

Static HTML site for Pro Tint DMV, the window tinting arm of the Pro Wash
family. Deploys to HostGator on every push to `main` via `deploy.php`
(GitHub push webhook, same setup as prowash-html; secrets live in the
gitignored `deploy-config.php` on the server). Sister repo: `branderboy/prowash-html` (shares the stylesheet,
nav.js, reveal.js and the Acuity booking account).

## Site structure (5 core elements)

1. Services: `services/*.html`, one page per package.
2. Service category: `services/index.html`.
3. Topical: `guides/*.html` (cost, laws, process, aftercare, comparison,
   problems) and `faq.html`.
4. Geo: `locations/*.html`, one per shop, each with the Google Business
   Profile map embed and that shop's Acuity booking link.
5. Trust: `about.html`, `warranty.html`, review quotes, standards.

## Writing rules

- NEVER use em dashes or en dashes anywhere. Use ` - ` or a comma.
- No middle dots as separators. Use commas or pipes.
- Phone everywhere: (301) 307-1414, tel links `tel:3013071414`.
- Hero tagline: "Get Your Pro Tint On". Do not use the Pro Wash tagline.
- Homepage hero photo is `images/protint-hero-home.jpg` (the black
  Cadillac). Never touch a hero unless asked.
- Internal link additions are plain text links, not buttons.
- "Business Hours", never "Facility Hours".

## Key facts

- HQ: Capitol Heights, 29 Hampton Park Blvd. Four shops: Capitol Heights,
  Bowie (4406 Crain Hwy, Suite B), Clinton (6311 Coventry Way, Suite B),
  Upper Marlboro (7538 Crain Hwy). No DC shop.
- Google listing names: "Pro Tint DMV - Capitol Heights", "Pro Tint DMV -
  Bowie", "Pro Tint - Clinton", "Pro Tint - Upper Marlboro".
- Pricing: cars $108 all windows, trucks $60 two front windows only.
  Always include "Additional windows / SUVs: call (301) 307-1414."
  SUVs, vans, ceramic and removal are call-for-quote.
- Film: Global Window Films dyed-carbon standard, 3M on request, ceramic
  upgrade. Lifetime warranty on every install. Free wash included.
- Legal: Maryland 35% VLT all windows on cars, 35% front doors on
  trucks/SUVs (Transp. Art. 22-406). The DC law guide (Code 50-2207.02:
  70% front / 50% rear; minivans 55% / 35%) is topical content only.
  NEVER say the business is in DC or serves DC as a location. Law
  guides carry a "checked on" date; update it when re-verified.
- Booking: Acuity owner 14099514, category filter
  `appointmentType=category:Window+Tinting`. Per-location calendars are in `book.html`.

## Before pushing

- New pages need canonical, OG + Twitter meta, favicon, JSON-LD, and the
  stylesheet link with the current `styles.css?v=` version.
- Bump `styles.css?v=` sitewide when CSS changes.
- Validate JSON-LD parses and internal links resolve.
