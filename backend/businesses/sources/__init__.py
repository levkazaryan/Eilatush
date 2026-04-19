"""Package of business/professional scrapers."""
from .eilat_city import scrape_eilat_city
from .yomyom_pros import scrape_yomyom_professionals

__all__ = [
    "scrape_eilat_city",
    "scrape_yomyom_professionals",
]
