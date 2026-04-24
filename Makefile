.PHONY: build serve scrape classify all clean help

help:
	@echo "SLAYBILL — make targets"
	@echo "  build      regenerate shows_live.json + show detail pages + archive"
	@echo "  serve      start local dev server on :8000"
	@echo "  scrape     run all scrapers (Playbill grosses + news + BroadwayWorld)"
	@echo "  classify   back-propagate events -> shows.status"
	@echo "  all        scrape + classify + build"
	@echo "  clean      remove generated files"

build:
	uv run --with Pillow python builders/build_live_shows.py
	uv run --with Pillow python builders/build_show_pages.py
	python builders/build_archive.py

serve:
	python -m http.server 8000 --directory web

scrape:
	uv run --with requests --with beautifulsoup4 python scrapers/playbill_grosses.py
	uv run --with requests --with beautifulsoup4 python scrapers/playbill_news.py
	uv run --with requests --with beautifulsoup4 python scrapers/broadway_world.py

classify:
	python builders/classify_status.py

all: scrape classify build

clean:
	rm -f data/shows_live.json
	rm -f web/archive.html
	find web/shows -maxdepth 1 -name '*.html' ! -name '_template.html' -delete
