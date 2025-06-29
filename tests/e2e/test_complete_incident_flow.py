"""
End-to-end tests for complete incident management flow
"""

import os
import json
import time
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List
import pytest
import requests
import websocket
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Configuration
API_ENDPOINT = os.environ.get('API_ENDPOINT', 'https://api.aegis.example.com')
FRONTEND_URL = os.environ.get('FRONTEND_URL', 'https://aegis.example.com')
TEST_USER_EMAIL = os.environ.get('TEST_USER_EMAIL', 'test@example.com')
TEST_USER_PASSWORD = os.environ.get('TEST_USER_PASSWORD', 'TestPassword123!')


class TestCompleteIncidentFlow:
    """End-to-end test for complete incident lifecycle."""
    
    @pytest.fixture
    def browser(self):
        """Set up browser for UI testing."""
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        
        driver = webdriver.Chrome(options=options)
        driver.implicitly_wait(10)
        
        yield driver
        
        driver.quit()
    
    @pytest.fixture
    def auth_token(self):
        """Get authentication token."""
        # In real implementation, would authenticate with Cognito
        return "test-auth-token"
    
    def test_complete_p0_incident_flow(self, browser, auth_token):
        """Test complete flow for P0 incident from creation to resolution."""
        start_time = datetime.utcnow()
        
        # Step 1: Create P0 incident via API
        incident_data = {
            "title": "CRITICAL: Payment Service Down",
            "description": "Payment processing service is completely unavailable. No transactions are being processed.",
            "severity": "P0",
            "source": "E2E Test",
            "metadata": {
                "service": "payment-service",
                "environment": "production",
                "error_rate": 100,
                "affected_customers": "all"
            }
        }
        
        response = requests.post(
            f"{API_ENDPOINT}/incidents",
            json=incident_data,
            headers={
                "Authorization": f"Bearer {auth_token}",
                "Content-Type": "application/json"
            }
        )
        
        assert response.status_code == 201
        incident = response.json()
        incident_id = incident['incidentId']
        
        print(f"Created P0 incident: {incident_id}")
        
        # Step 2: Verify immediate notifications
        time.sleep(5)  # Wait for notifications
        
        # Check that incident appears in active incidents
        response = requests.get(
            f"{API_ENDPOINT}/incidents?status=OPEN&severity=P0",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        assert response.status_code == 200
        active_incidents = response.json()['items']
        assert any(i['id'] == incident_id for i in active_incidents)
        
        # Step 3: Access incident via UI
        browser.get(FRONTEND_URL)
        
        # Login
        self._login(browser, TEST_USER_EMAIL, TEST_USER_PASSWORD)
        
        # Navigate to incident
        browser.get(f"{FRONTEND_URL}/incidents/{incident_id}")
        
        # Wait for page load
        wait = WebDriverWait(browser, 10)
        incident_title = wait.until(
            EC.presence_of_element_located((By.TAG_NAME, "h4"))
        )
        
        assert "Payment Service Down" in incident_title.text
        
        # Step 4: Acknowledge incident
        acknowledge_btn = browser.find_element(By.XPATH, "//button[contains(text(), 'Acknowledge')]")
        acknowledge_btn.click()
        
        # Wait for status update
        time.sleep(2)
        
        # Verify acknowledged via API
        response = requests.get(
            f"{API_ENDPOINT}/incidents/{incident_id}",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        assert response.status_code == 200
        assert response.json()['status'] == 'ACKNOWLEDGED'
        assert response.json()['acknowledgedAt'] is not None
        
        # Step 5: Add investigation comment
        comment_text = "Investigating database connection issues. Appears to be network-related."
        
        response = requests.post(
            f"{API_ENDPOINT}/incidents/{incident_id}/comments",
            json={"text": comment_text},
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        assert response.status_code == 201
        
        # Step 6: Update status to MITIGATING
        response = requests.patch(
            f"{API_ENDPOINT}/incidents/{incident_id}/status",
            json={
                "status": "MITIGATING",
                "reason": "Implementing database connection pool expansion"
            },
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        assert response.status_code == 200
        
        # Step 7: Simulate mitigation progress
        time.sleep(10)
        
        # Add resolution comment
        response = requests.post(
            f"{API_ENDPOINT}/incidents/{incident_id}/comments",
            json={
                "text": "Connection pool expanded. Service is recovering. Monitoring for stability."
            },
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        # Step 8: Resolve incident
        response = requests.post(
            f"{API_ENDPOINT}/incidents/{incident_id}/resolve",
            json={
                "resolution": "Increased database connection pool size from 100 to 500. Service restored."
            },
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        assert response.status_code == 200
        resolved_incident = response.json()
        assert resolved_incident['status'] == 'RESOLVED'
        assert resolved_incident['resolvedAt'] is not None
        
        # Step 9: Verify AI post-mortem generation
        time.sleep(15)  # Wait for AI processing
        
        response = requests.get(
            f"{API_ENDPOINT}/incidents/{incident_id}",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        incident_data = response.json()
        
        # Check for AI summaries
        assert len(incident_data.get('aiSummaries', [])) > 0
        
        # Check timeline has post-mortem
        timeline = incident_data.get('timeline', [])
        post_mortem_events = [e for e in timeline if e['type'] == 'POST_MORTEM_GENERATED']
        assert len(post_mortem_events) > 0
        
        # Step 10: Calculate and verify metrics
        end_time = datetime.utcnow()
        total_duration = (end_time - start_time).total_seconds() / 60
        
        print(f"Incident lifecycle completed in {total_duration:.1f} minutes")
        
        # Verify resolution time is tracked
        assert incident_data.get('metadata', {}).get('resolution_time_minutes') is not None
        
        # Step 11: Close incident
        response = requests.post(
            f"{API_ENDPOINT}/incidents/{incident_id}/close",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        assert response.status_code == 200
        assert response.json()['status'] == 'CLOSED'
        
        print(f"Successfully completed P0 incident flow for {incident_id}")
    
    def test_concurrent_incident_handling(self, auth_token):
        """Test system handling multiple concurrent incidents."""
        num_incidents = 5
        incident_ids = []
        
        # Create multiple incidents concurrently
        async def create_incident(index):
            incident_data = {
                "title": f"Concurrent Test Incident {index}",
                "description": f"Testing concurrent incident handling - {index}",
                "severity": "P2",
                "source": "E2E Concurrent Test",
                "metadata": {
                    "test_index": index,
                    "service": f"service-{index % 3}"
                }
            }
            
            response = requests.post(
                f"{API_ENDPOINT}/incidents",
                json=incident_data,
                headers={"Authorization": f"Bearer {auth_token}"}
            )
            
            return response.json()['incidentId']
        
        # Create incidents
        loop = asyncio.new_event_loop()
        tasks = [create_incident(i) for i in range(num_incidents)]
        incident_ids = loop.run_until_complete(asyncio.gather(*tasks))
        
        print(f"Created {len(incident_ids)} concurrent incidents")
        
        # Verify all incidents were created
        response = requests.get(
            f"{API_ENDPOINT}/incidents?status=OPEN&limit=50",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        open_incidents = response.json()['items']
        for incident_id in incident_ids:
            assert any(i['id'] == incident_id for i in open_incidents)
        
        # Process incidents concurrently
        async def process_incident(incident_id):
            # Acknowledge
            requests.post(
                f"{API_ENDPOINT}/incidents/{incident_id}/acknowledge",
                headers={"Authorization": f"Bearer {auth_token}"}
            )
            
            # Add comment
            requests.post(
                f"{API_ENDPOINT}/incidents/{incident_id}/comments",
                json={"text": f"Processing {incident_id}"},
                headers={"Authorization": f"Bearer {auth_token}"}
            )
            
            # Resolve
            requests.post(
                f"{API_ENDPOINT}/incidents/{incident_id}/resolve",
                json={"resolution": "Automated resolution"},
                headers={"Authorization": f"Bearer {auth_token}"}
            )
        
        # Process all incidents
        tasks = [process_incident(iid) for iid in incident_ids]
        loop.run_until_complete(asyncio.gather(*tasks))
        
        # Verify all incidents are resolved
        for incident_id in incident_ids:
            response = requests.get(
                f"{API_ENDPOINT}/incidents/{incident_id}",
                headers={"Authorization": f"Bearer {auth_token}"}
            )
            assert response.json()['status'] == 'RESOLVED'
        
        print(f"Successfully processed {num_incidents} concurrent incidents")
    
    def test_real_time_updates(self, auth_token):
        """Test real-time updates via WebSocket."""
        # Create incident
        response = requests.post(
            f"{API_ENDPOINT}/incidents",
            json={
                "title": "Real-time Test Incident",
                "severity": "P2",
                "source": "E2E Test"
            },
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        incident_id = response.json()['incidentId']
        
        # Connect to WebSocket for real-time updates
        ws_url = API_ENDPOINT.replace('https://', 'wss://').replace('http://', 'ws://')
        ws = websocket.WebSocket()
        
        # Subscribe to incident updates
        ws.connect(f"{ws_url}/ws")
        ws.send(json.dumps({
            "action": "subscribe",
            "incident_id": incident_id,
            "auth_token": auth_token
        }))
        
        # Update incident status
        requests.patch(
            f"{API_ENDPOINT}/incidents/{incident_id}/status",
            json={"status": "ACKNOWLEDGED"},
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        # Wait for WebSocket update
        result = ws.recv()
        update = json.loads(result)
        
        assert update['type'] == 'status_change'
        assert update['incident_id'] == incident_id
        assert update['new_status'] == 'ACKNOWLEDGED'
        
        ws.close()
        
        print("Real-time updates working correctly")
    
    def test_dashboard_metrics(self, browser, auth_token):
        """Test dashboard displays correct metrics."""
        # Login to dashboard
        browser.get(FRONTEND_URL)
        self._login(browser, TEST_USER_EMAIL, TEST_USER_PASSWORD)
        
        # Navigate to dashboard
        browser.get(f"{FRONTEND_URL}/dashboard")
        
        # Wait for metrics to load
        wait = WebDriverWait(browser, 10)
        total_incidents = wait.until(
            EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'metric-card')]//h4"))
        )
        
        # Get metrics from API
        response = requests.get(
            f"{API_ENDPOINT}/metrics/dashboard",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        api_metrics = response.json()
        
        # Verify UI shows correct metrics
        ui_total = int(total_incidents.text)
        assert ui_total == api_metrics['totalIncidents']
        
        print("Dashboard metrics validation passed")
    
    def _login(self, browser, email, password):
        """Helper to login via UI."""
        # Find login form
        email_input = browser.find_element(By.NAME, "email")
        password_input = browser.find_element(By.NAME, "password")
        
        email_input.send_keys(email)
        password_input.send_keys(password)
        
        # Submit
        login_button = browser.find_element(By.XPATH, "//button[@type='submit']")
        login_button.click()
        
        # Wait for redirect
        WebDriverWait(browser, 10).until(
            EC.url_contains("/dashboard")
        )


class TestPerformanceAndScale:
    """Test system performance and scalability."""
    
    def test_api_response_times(self, auth_token):
        """Test API response times under load."""
        endpoints = [
            ("GET", "/incidents?status=OPEN"),
            ("GET", "/incidents/INC-001"),
            ("GET", "/metrics/dashboard")
        ]
        
        results = {}
        
        for method, path in endpoints:
            times = []
            
            # Make 100 requests
            for _ in range(100):
                start = time.time()
                
                if method == "GET":
                    response = requests.get(
                        f"{API_ENDPOINT}{path}",
                        headers={"Authorization": f"Bearer {auth_token}"}
                    )
                
                end = time.time()
                times.append((end - start) * 1000)  # Convert to ms
            
            # Calculate statistics
            avg_time = sum(times) / len(times)
            p95_time = sorted(times)[int(len(times) * 0.95)]
            p99_time = sorted(times)[int(len(times) * 0.99)]
            
            results[path] = {
                "avg": avg_time,
                "p95": p95_time,
                "p99": p99_time
            }
            
            print(f"{method} {path}: avg={avg_time:.1f}ms, p95={p95_time:.1f}ms, p99={p99_time:.1f}ms")
            
            # Assert performance requirements
            assert avg_time < 100  # Average under 100ms
            assert p95_time < 200  # 95th percentile under 200ms
            assert p99_time < 500  # 99th percentile under 500ms
        
        return results
    
    def test_concurrent_load(self, auth_token):
        """Test system under concurrent load."""
        num_threads = 10
        requests_per_thread = 50
        
        import threading
        import queue
        
        errors = queue.Queue()
        response_times = queue.Queue()
        
        def worker():
            for _ in range(requests_per_thread):
                try:
                    start = time.time()
                    response = requests.get(
                        f"{API_ENDPOINT}/incidents",
                        headers={"Authorization": f"Bearer {auth_token}"}
                    )
                    end = time.time()
                    
                    if response.status_code != 200:
                        errors.put(f"Status {response.status_code}")
                    
                    response_times.put((end - start) * 1000)
                    
                except Exception as e:
                    errors.put(str(e))
        
        # Start threads
        threads = []
        for _ in range(num_threads):
            t = threading.Thread(target=worker)
            t.start()
            threads.append(t)
        
        # Wait for completion
        for t in threads:
            t.join()
        
        # Analyze results
        error_count = errors.qsize()
        total_requests = num_threads * requests_per_thread
        error_rate = (error_count / total_requests) * 100
        
        print(f"Total requests: {total_requests}")
        print(f"Errors: {error_count} ({error_rate:.1f}%)")
        
        # Assert error rate is acceptable
        assert error_rate < 1.0  # Less than 1% error rate
        
        # Analyze response times
        times = []
        while not response_times.empty():
            times.append(response_times.get())
        
        avg_time = sum(times) / len(times)
        print(f"Average response time under load: {avg_time:.1f}ms")
        
        assert avg_time < 200  # Average under 200ms even under load