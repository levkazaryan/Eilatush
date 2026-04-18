# Test news API endpoints
import pytest
import requests

class TestNews:
    """News API tests"""

    def test_get_all_news(self, api_client, base_url):
        """Test GET /api/news returns 6 Hebrew news items"""
        response = api_client.get(f"{base_url}/api/news")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        assert len(data) >= 6, f"Expected at least 6 news items, got {len(data)}"
        
        # Verify first news item has required fields
        news = data[0]
        assert "id" in news
        assert "title" in news
        assert "source" in news
        assert "published_at" in news
        
        # Verify Hebrew content
        assert any(ord(c) >= 0x0590 and ord(c) <= 0x05FF for c in news["title"]), "Title should contain Hebrew"

    def test_news_sorted_newest_first(self, api_client, base_url):
        """Test news are sorted by published_at (newest first)"""
        response = api_client.get(f"{base_url}/api/news")
        assert response.status_code == 200
        
        data = response.json()
        if len(data) > 1:
            # Verify reverse chronological order
            from datetime import datetime
            prev_time = None
            for news in data:
                current_time = datetime.fromisoformat(news["published_at"].replace('Z', '+00:00'))
                if prev_time:
                    assert current_time <= prev_time, "News should be sorted newest first"
                prev_time = current_time

    def test_filter_news_by_source_municipality(self, api_client, base_url):
        """Test GET /api/news?source=municipality"""
        response = api_client.get(f"{base_url}/api/news?source=municipality")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0, "Should have at least one municipality news item"
        
        for news in data:
            assert news.get("source") == "municipality", f"Expected source=municipality, got {news.get('source')}"

    def test_news_sources(self, api_client, base_url):
        """Test news have valid sources"""
        response = api_client.get(f"{base_url}/api/news")
        assert response.status_code == 200
        
        data = response.json()
        valid_sources = ["municipality", "alert", "event"]
        for news in data:
            assert news.get("source") in valid_sources, f"Invalid source: {news.get('source')}"
