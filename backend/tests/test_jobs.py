# Test jobs API endpoints
import pytest
import requests

class TestJobs:
    """Jobs API tests"""

    def test_get_all_jobs(self, api_client, base_url):
        """Test GET /api/jobs returns 6 jobs sorted by urgency"""
        response = api_client.get(f"{base_url}/api/jobs")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        assert len(data) >= 6, f"Expected at least 6 jobs, got {len(data)}"
        
        # Verify first job has required fields
        job = data[0]
        assert "id" in job
        assert "title" in job
        assert "urgency" in job
        assert job["urgency"] in ["now", "soon", "this_week"], f"Invalid urgency: {job['urgency']}"
        
        # Verify Hebrew content
        assert any(ord(c) >= 0x0590 and ord(c) <= 0x05FF for c in job["title"]), "Title should contain Hebrew"

    def test_jobs_sorted_by_urgency(self, api_client, base_url):
        """Test jobs are sorted by urgency (now first)"""
        response = api_client.get(f"{base_url}/api/jobs")
        assert response.status_code == 200
        
        data = response.json()
        if len(data) > 1:
            # Verify urgency order: now > soon > this_week
            urgency_order = {"now": 0, "soon": 1, "this_week": 2}
            prev_order = -1
            for job in data:
                current_order = urgency_order.get(job["urgency"], 3)
                assert current_order >= prev_order, f"Jobs should be sorted by urgency, got {job['urgency']} after order {prev_order}"
                prev_order = current_order

    def test_filter_jobs_by_urgency_now(self, api_client, base_url):
        """Test GET /api/jobs?urgency=now"""
        response = api_client.get(f"{base_url}/api/jobs?urgency=now")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0, "Should have at least one urgent job"
        
        for job in data:
            assert job.get("urgency") == "now", f"Expected urgency=now, got {job.get('urgency')}"

    def test_filter_jobs_by_category_hotel(self, api_client, base_url):
        """Test GET /api/jobs?category=hotel"""
        response = api_client.get(f"{base_url}/api/jobs?category=hotel")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0, "Should have at least one hotel job"
        
        for job in data:
            assert job.get("category") == "hotel", f"Expected category=hotel, got {job.get('category')}"

    def test_jobs_have_posted_at(self, api_client, base_url):
        """Test jobs have posted_at timestamp"""
        response = api_client.get(f"{base_url}/api/jobs")
        assert response.status_code == 200
        
        data = response.json()
        for job in data:
            assert "posted_at" in job, "Job should have posted_at field"
