"""Per-source scrapers — one module per news source (or cluster).
"""
from .muni import scrape_eilat_muni_articles, scrape_eilat_muni_mivzak
from .smarticket import scrape_smarticket
from .ynet import scrape_ynet_eilat, YNET_RSS_CANDIDATES
from .kan import scrape_kan_eilat
from .tag_pages import (
    scrape_israelhayom_eilat,
    scrape_maariv_eilat,
    scrape_globes_eilat,
    scrape_davar_eilat,
    scrape_walla_eilat,
)
from .mako import scrape_mako_eilat
from .hamal import scrape_hamal
from .facebook import scrape_facebook_eilat_muni
