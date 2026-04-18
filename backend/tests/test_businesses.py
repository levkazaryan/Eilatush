# Test businesses API endpoints
import pytest
import requests

class TestBusinesses:
    """Businesses API tests"""

    def test_get_all_businesses(self, api_client, base_url):
        """Test GET /api/businesses returns Hebrew seeded businesses"""
        response = api_client.get(f"{base_url}/api/businesses")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        assert len(data) >= 12, f"Expected at least 12 businesses, got {len(data)}"
        
        # Verify first business has required fields and open_now computed
        biz = data[0]
        assert "id" in biz
        assert "name" in biz
        assert "open_now" in biz, "Business should have computed 'open_now' field"
        assert isinstance(biz["open_now"], bool), "open_now should be boolean"
        
        # Verify Hebrew content
        assert any(ord(c) >= 0x0590 and ord(c) <= 0x05FF for c in biz["name"]), "Name should contain Hebrew"

    def test_filter_businesses_open_now(self, api_client, base_url):
        """Test GET /api/businesses?open_now=true"""
        response = api_client.get(f"{base_url}/api/businesses?open_now=true")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        
        # All returned businesses should have open_now=true
        for biz in data:
            assert biz.get("open_now") is True, f"Expected open_now=true, got {biz.get('open_now')}"

    def test_filter_businesses_by_category_bar(self, api_client, base_url):
        """Test GET /api/businesses?category=bar"""
        response = api_client.get(f"{base_url}/api/businesses?category=bar")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0, "Should have at least one bar"
        
        for biz in data:
            assert biz.get("category") == "bar", f"Expected category=bar, got {biz.get('category')}"

    def test_search_businesses_sushi(self, api_client, base_url):
        """Test GET /api/businesses?q=סושי (search for sushi)"""
        response = api_client.get(f"{base_url}/api/businesses?q=סושי")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0, "Should find at least one sushi business"
        
        # Verify search matches name, description, or tags
        found = False
        for biz in data:
            if "סושי" in biz.get("name", "") or "סושי" in biz.get("description", "") or "סושי" in " ".join(biz.get("tags", [])):
                found = True
                break
        assert found, "Search results should contain 'סושי' in name, description, or tags"

    def test_businesses_have_rating(self, api_client, base_url):
        """Test businesses have rating field"""
        response = api_client.get(f"{base_url}/api/businesses")
        assert response.status_code == 200
        
        data = response.json()
        for biz in data:
            assert "rating" in biz
            assert isinstance(biz["rating"], (int, float))
            assert 0 <= biz["rating"] <= 5, f"Rating should be 0-5, got {biz['rating']}"
