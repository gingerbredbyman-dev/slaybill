.PHONY: build serve scrape classify all clean help publish

help:
	@echo "SLAYBILL — make targets"
	@echo "  build      regenerate shows_live.json + show detail pages + archive"
	@echo "  serve      start local dev server on :8000"
	@echo "  scrape     run all scrapers (Playbill grosses + news + BroadwayWorld)"
	@echo "  classify   back-propagate events -> shows.status"
	@echo "  all        scrape + classify + build"
	@echo "  publish    build + sync web/ -> docs/ + commit + push to GitHub Pages"
	@echo "  clean      remove generated files"

build:
	uv run --with Pillow python builders/build_live_shows.py
	uv run --with Pillow python builders/build_show_pages.py
	python3 builders/build_archive.py

serve:
	python -m http.server 8000 --directory web

scrape:
	uv run --with requests --with beautifulsoup4 python scrapers/playbill_grosses.py
	uv run --with requests --with beautifulsoup4 python scrapers/playbill_news.py
	uv run --with requests --with beautifulsoup4 python scrapers/broadway_world.py

classify:
	python builders/classify_status.py

all: scrape classify build

# One-line ship: build, mirror web/ to docs/, commit, push to GitHub Pages.
# Live URL: https://gingerbredbyman-dev.github.io/slaybill/
publish: build
	rsync -a --delete web/ docs/
	git add -A
	git diff --cached --quiet || git commit -m "publish: refresh docs/ from web/ build"
	git push origin main

clean:
	rm -f data/shows_live.json
	rm -f web/archive.html
	find web/shows -maxdepth 1 -name '*.html' ! -name '_template.html' -delete
