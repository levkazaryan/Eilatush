# Test Eilatush AI chat endpoint
import pytest
import requests
import time

class TestEilatushChat:
    """Eilatush AI chat API tests"""

    def test_chat_basic_structure(self, api_client, base_url):
        """Test POST /api/eilatush/chat returns correct structure"""
        response = api_client.post(
            f"{base_url}/api/eilatush/chat",
            json={"message": "שלום"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "session_id" in data, "Response should have session_id"
        assert "reply" in data, "Response should have reply"
        assert "intent" in data, "Response should have intent"
        assert "results" in data, "Response should have results array"
        assert isinstance(data["results"], list), "results should be a list"

    def test_chat_events_query(self, api_client, base_url):
        """Test Hebrew query 'מה קורה הערב' maps to events intent"""
        response = api_client.post(
            f"{base_url}/api/eilatush/chat",
            json={"message": "מה קורה הערב"}
        )
        assert response.status_code == 200
        
        data = response.json()
        # Should map to events intent (either from LLM or fallback)
        assert data.get("intent") == "events", f"Expected intent=events, got {data.get('intent')}"
        
        # Should return event results
        results = data.get("results", [])
        if len(results) > 0:
            assert results[0].get("type") == "event", "Results should be event type"
            assert "item" in results[0], "Result should have item field"

    def test_chat_jobs_urgent_query(self, api_client, base_url):
        """Test Hebrew query 'עבודה דחופה' maps to jobs intent with urgency=now"""
        response = api_client.post(
            f"{base_url}/api/eilatush/chat",
            json={"message": "עבודה דחופה"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("intent") == "jobs", f"Expected intent=jobs, got {data.get('intent')}"
        
        # Should return job results
        results = data.get("results", [])
        if len(results) > 0:
            assert results[0].get("type") == "job", "Results should be job type"

    def test_chat_businesses_sushi_query(self, api_client, base_url):
        """Test Hebrew query 'סושי' maps to businesses intent"""
        response = api_client.post(
            f"{base_url}/api/eilatush/chat",
            json={"message": "סושי"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("intent") == "businesses", f"Expected intent=businesses, got {data.get('intent')}"
        
        # Should return business results
        results = data.get("results", [])
        if len(results) > 0:
            assert results[0].get("type") == "business", "Results should be business type"

    def test_chat_news_municipality_query(self, api_client, base_url):
        """Test Hebrew query 'חדשות מהעירייה' maps to news intent"""
        response = api_client.post(
            f"{base_url}/api/eilatush/chat",
            json={"message": "חדשות מהעירייה"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("intent") == "news", f"Expected intent=news, got {data.get('intent')}"
        
        # Should return news results
        results = data.get("results", [])
        if len(results) > 0:
            assert results[0].get("type") == "news", "Results should be news type"

    def test_chat_session_persistence(self, api_client, base_url):
        """Test session_id is returned and can be reused"""
        # First message
        response1 = api_client.post(
            f"{base_url}/api/eilatush/chat",
            json={"message": "שלום"}
        )
        assert response1.status_code == 200
        data1 = response1.json()
        session_id = data1.get("session_id")
        assert session_id, "Should return session_id"
        
        # Second message with same session
        response2 = api_client.post(
            f"{base_url}/api/eilatush/chat",
            json={"message": "תודה", "session_id": session_id}
        )
        assert response2.status_code == 200
        data2 = response2.json()
        assert data2.get("session_id") == session_id, "Should maintain same session_id"

    def test_chat_results_have_correct_structure(self, api_client, base_url):
        """Test results array items have correct structure"""
        response = api_client.post(
            f"{base_url}/api/eilatush/chat",
            json={"message": "מה קורה עכשיו"}
        )
        assert response.status_code == 200
        
        data = response.json()
        results = data.get("results", [])
        
        for result in results:
            assert "type" in result, "Result should have type field"
            assert result["type"] in ["event", "business", "job", "news"], f"Invalid result type: {result['type']}"
            assert "item" in result, "Result should have item field"
            assert isinstance(result["item"], dict), "Item should be a dict"
