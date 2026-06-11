# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

Static website for **Faches-Thumesnil Tennis de Table (F3T)**, a French table tennis club. It is built with [Hugo](https://gohugo.io/) and hosted on GitHub Pages (`master` branch contains only `public/`). Development happens on the `gohugo` branch.

## Build & run

```sh
# Local dev server (hot-reload)
hugo server

# Full production build (also fetches Facebook posts + writes CNAME)
sh generateSite.sh     # requires $facebook_token env var (see .env)

# Generate PDFs from docs/ markdown files (requires pandoc/latex Docker image)
sh generatePdf.sh
```

Secrets are loaded from `.env` (gitignored). The CI workflow (`jhanos/hugo` Docker image) runs `generateSite.sh` then `generatePdf.sh` and commits the result to `master` via `git subtree split -P public`.

## Architecture

### Theme: `themes/f3t` (custom)

The active theme is **`f3t`** — a fully custom Tailwind CSS theme that replaced the bundled `hugo-tranquilpeak-theme`. Tailwind is loaded via CDN in `baseof.html`, so there is no build step for CSS.

Layout hierarchy:
- `themes/f3t/layouts/_default/baseof.html` — HTML shell, Tailwind config, header/footer partials
- `themes/f3t/layouts/index.html` — homepage (hero, news feed, sponsors)
- `themes/f3t/layouts/_default/single.html` / `list.html` — post pages
- `themes/f3t/layouts/pages/` — individual static pages (contact, horaires, infos, inscription)
- `themes/f3t/layouts/partials/` — `header.html`, `footer.html`, `post-card.html`

The `hugo-tranquilpeak-theme` directory is present but **not active** — do not edit it.

### Content

- `content/post/` — news articles (Markdown). Posts are auto-generated from Facebook by `generateSite.sh` using the Graph API; filenames use the Facebook post ID (e.g. `1909136939359253_123.md`). Manually created posts can also be placed here.
- `content/pages/` — static club info pages (contact, equipes, horaires, inscription, results).
- `docs/` — meeting minutes and club documents (Markdown + PDF). `generatePdf.sh` converts `.md` files to PDF and copies both to `public/docs/<year>/`.
- `static/` — images, PDFs (inscription forms, tournament rules), accessible as `/images/…`.

### Site config

`config.toml` defines base URL, menus, taxonomy, and theme parameters. The club's brand color is `#1e40af` (Tailwind `blue-800`), configured in the Tailwind theme extension in `baseof.html`.

### External data

- **Facebook Graph API** (`generateSite.sh`): fetches the 15 most recent posts from page `1909136939359253`, creates missing `content/post/<id>.md` files with front matter.
- **FFTT API** (`api_fftt.py`): fetches team match results from the French table tennis federation. Currently commented out in `generateSite.sh`. Club number: `07590074`, auth ID: `SW790`.

### CI/CD

`.github/workflows/gohugo.yml` triggers on every push and daily at 06:00 UTC. It:
1. Runs `generateSite.sh` inside `jhanos/hugo` (builds Hugo + fetches FB posts)
2. Runs `generatePdf.sh` inside `pandoc/latex`
3. Commits all changes back to `gohugo`, then force-pushes only `public/` to `master` via `git subtree split`

The live site is served from `master`; `gohugo` is the working branch.
