# Test events API endpoints
import pytest
import requests

class TestEvents:
    """Events API tests"""

    def test_get_all_events(self, api_client, base_url):
        """Test GET /api/events returns Hebrew seeded events"""
        response = api_client.get(f"{base_url}/api/events")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        assert len(data) >= 8, f"Expected at least 8 events, got {len(data)}"
        
        # Verify first event has required fields and band computed
        event = data[0]
        assert "id" in event
        assert "title" in event
        assert "band" in event, "Event should have computed 'band' field"
        assert event["band"] in ["now", "tonight", "later"], f"Invalid band: {event['band']}"
        
        # Verify Hebrew content
        assert any(ord(c) >= 0x0590 and ord(c) <= 0x05FF for c in event["title"]), "Title should contain Hebrew"

    def test_filter_events_by_band_now(self, api_client, base_url):
        """Test GET /api/events?band=now"""
        response = api_client.get(f"{base_url}/api/events?band=now")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        
        # All returned events should have band=now
        for event in data:
            assert event.get("band") == "now", f"Expected band=now, got {event.get('band')}"

    def test_filter_events_by_band_tonight(self, api_client, base_url):
        """Test GET /api/events?band=tonight"""
        response = api_client.get(f"{base_url}/api/events?band=tonight")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        
        for event in data:
            assert event.get("band") == "tonight", f"Expected band=tonight, got {event.get('band')}"

    def test_filter_events_by_band_later(self, api_client, base_url):
        """Test GET /api/events?band=later"""
        response = api_client.get(f"{base_url}/api/events?band=later")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        
        for event in data:
            assert event.get("band") == "later", f"Expected band=later, got {event.get('band')}"

    def test_filter_events_by_category_party(self, api_client, base_url):
        """Test GET /api/events?category=party"""
        response = api_client.get(f"{base_url}/api/events?category=party")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0, "Should have at least one party event"
        
        for event in data:
            assert event.get("category") == "party", f"Expected category=party, got {event.get('category')}"

    def test_events_sorted_by_start_time(self, api_client, base_url):
        """Test events are sorted by starts_at"""
        response = api_client.get(f"{base_url}/api/events")
        assert response.status_code == 200
        
        data = response.json()
        if len(data) > 1:
            # Verify chronological order
            from datetime import datetime
            prev_time = None
            for event in data:
                current_time = datetime.fromisoformat(event["starts_at"].replace('Z', '+00:00'))
                if prev_time:
                    assert current_time >= prev_time, "Events should be sorted by starts_at"
                prev_time = current_time
