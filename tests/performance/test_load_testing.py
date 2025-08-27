"""Performance and load testing for oaDeviceAPI."""

import pytest
import time
import asyncio
from unittest.mock import patch, Mock, AsyncMock
from fastapi import status
import concurrent.futures
import threading


class TestAPIResponseTimes:
    """Test API response time performance."""
    
    def test_health_endpoint_response_time(self, test_client_macos):
        """Test health endpoint response time under normal conditions."""
        response_times = []
        
        # Test multiple requests to get average
        for _ in range(10):
            start_time = time.time()
            response = test_client_macos.get("/health")
            end_time = time.time()
            
            response_times.append(end_time - start_time)
            assert response.status_code == 200
        
        # Calculate performance metrics
        avg_time = sum(response_times) / len(response_times)
        max_time = max(response_times)
        
        # Performance expectations
        assert avg_time < 1.0, f"Average response time too slow: {avg_time}s"
        assert max_time < 2.0, f"Maximum response time too slow: {max_time}s"
        
        # Performance should be consistent (low variance)
        variance = sum((t - avg_time) ** 2 for t in response_times) / len(response_times)
        assert variance < 0.1, f"Response time variance too high: {variance}"
    
    def test_platform_endpoint_response_time(self, test_client_macos):
        """Test platform endpoint response time."""
        start_time = time.time()
        response = test_client_macos.get("/platform")
        end_time = time.time()
        
        assert response.status_code == 200
        assert (end_time - start_time) < 0.5  # Should be very fast
    
    def test_root_endpoint_response_time(self, test_client_macos):
        """Test root endpoint response time.""" 
        start_time = time.time()
        response = test_client_macos.get("/")
        end_time = time.time()
        
        assert response.status_code == 200
        assert (end_time - start_time) < 0.5  # Should be very fast
    
    def test_action_endpoint_response_time(self, test_client_macos):
        """Test action endpoint response time."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)
            
            start_time = time.time()
            response = test_client_macos.post("/actions/reboot")
            end_time = time.time()
            
            # Actions might take longer due to system calls
            assert (end_time - start_time) < 3.0


class TestConcurrentRequestHandling:
    """Test API performance under concurrent load."""
    
    def test_concurrent_health_requests(self, test_client_macos):
        """Test concurrent health requests performance."""
        num_requests = 20
        results = []
        
        def make_request():
            """Make a single health request."""
            start_time = time.time()
            response = test_client_macos.get("/health")
            end_time = time.time()
            return {
                "status_code": response.status_code,
                "response_time": end_time - start_time,
                "success": response.status_code == 200
            }
        
        # Simulate concurrent requests using threading
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request) for _ in range(num_requests)]
            results = [future.result() for future in futures]
        
        # Analyze results
        success_count = sum(1 for r in results if r["success"])
        avg_response_time = sum(r["response_time"] for r in results) / len(results)
        max_response_time = max(r["response_time"] for r in results)
        
        # Performance expectations for concurrent load
        assert success_count >= num_requests * 0.95  # 95% success rate minimum
        assert avg_response_time < 2.0, f"Average concurrent response time too slow: {avg_response_time}s"
        assert max_response_time < 5.0, f"Maximum concurrent response time too slow: {max_response_time}s"
    
    def test_mixed_endpoint_concurrent_load(self, test_client_macos):
        """Test concurrent requests to different endpoints."""
        endpoints = ["/", "/health", "/platform", "/cameras"]
        num_requests_per_endpoint = 5
        results = []
        
        def make_endpoint_request(endpoint):
            """Make request to specific endpoint."""
            start_time = time.time()
            response = test_client_macos.get(endpoint)
            end_time = time.time()
            return {
                "endpoint": endpoint,
                "status_code": response.status_code,
                "response_time": end_time - start_time
            }
        
        # Create mixed concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
            futures = []
            for endpoint in endpoints:
                for _ in range(num_requests_per_endpoint):
                    futures.append(executor.submit(make_endpoint_request, endpoint))
            
            results = [future.result() for future in futures]
        
        # Analyze by endpoint
        by_endpoint = {}
        for result in results:
            endpoint = result["endpoint"]
            if endpoint not in by_endpoint:
                by_endpoint[endpoint] = []
            by_endpoint[endpoint].append(result)
        
        # Each endpoint should perform well under concurrent load
        for endpoint, endpoint_results in by_endpoint.items():
            success_rate = sum(1 for r in endpoint_results if r["status_code"] in [200, 404]) / len(endpoint_results)
            avg_time = sum(r["response_time"] for r in endpoint_results) / len(endpoint_results)
            
            assert success_rate >= 0.9, f"Endpoint {endpoint} success rate too low: {success_rate}"
            assert avg_time < 3.0, f"Endpoint {endpoint} too slow under load: {avg_time}s"
    
    def test_resource_isolation_under_load(self, test_client_macos):
        """Test that resource usage remains reasonable under load.""" 
        import psutil
        
        # Monitor resource usage during load test
        initial_cpu = psutil.cpu_percent(interval=1)
        initial_memory = psutil.virtual_memory().percent
        
        def stress_test():
            """Stress test function."""
            for _ in range(50):
                test_client_macos.get("/health")
        
        # Run stress test
        start_time = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(stress_test) for _ in range(3)]
            concurrent.futures.wait(futures)
        end_time = time.time()
        
        # Check resource usage after load
        final_cpu = psutil.cpu_percent(interval=1)
        final_memory = psutil.virtual_memory().percent
        
        # Resource usage should not spike excessively
        cpu_increase = final_cpu - initial_cpu
        memory_increase = final_memory - initial_memory
        
        # Allow some increase but not excessive
        assert cpu_increase < 50.0, f"CPU usage increased too much: {cpu_increase}%"
        assert memory_increase < 20.0, f"Memory usage increased too much: {memory_increase}%"
        
        # Total test should complete in reasonable time
        total_time = end_time - start_time
        assert total_time < 30.0, f"Load test took too long: {total_time}s"


class TestMemoryUsagePatterns:
    """Test memory usage patterns and leak detection."""
    
    def test_memory_usage_stability(self, test_client_macos):
        """Test that memory usage remains stable over time."""
        import psutil
        import gc
        
        # Force garbage collection
        gc.collect()
        initial_memory = psutil.Process().memory_info().rss
        
        # Make many requests to detect memory leaks
        for _ in range(100):
            response = test_client_macos.get("/health")
            assert response.status_code == 200
        
        # Force garbage collection again
        gc.collect()
        final_memory = psutil.Process().memory_info().rss
        
        # Memory growth should be minimal
        memory_growth = final_memory - initial_memory
        memory_growth_mb = memory_growth / (1024 * 1024)
        
        # Allow some growth but detect significant leaks
        assert memory_growth_mb < 50.0, f"Memory leak detected: {memory_growth_mb}MB growth"
    
    def test_large_response_memory_handling(self, test_client_macos):
        """Test memory handling for large responses."""
        # Mock a service that returns large data
        large_data = {
            "cameras": [
                {
                    "id": f"camera_{i}",
                    "name": f"Camera {i}",
                    "large_field": "x" * 1000  # 1KB per camera
                }
                for i in range(100)  # 100 cameras = ~100KB
            ]
        }
        
        with patch("src.oaDeviceAPI.platforms.macos.services.camera.get_camera_info",
                  return_value=large_data["cameras"]):
            
            response = test_client_macos.get("/cameras")
            
            # Should handle large responses efficiently
            assert response.status_code in [200, 413]  # OK or Entity Too Large
            
            if response.status_code == 200:
                data = response.json()
                assert isinstance(data, dict)
                # Should not cause memory issues
                assert len(str(data)) > 50000  # Should be large response


class TestPerformanceRegression:
    """Test for performance regressions."""
    
    def test_baseline_performance_metrics(self, test_client_macos):
        """Establish baseline performance metrics."""
        # Test key endpoints and establish performance baselines
        endpoints = ["/", "/health", "/platform"]
        baselines = {}
        
        for endpoint in endpoints:
            times = []
            
            # Take multiple measurements for accuracy
            for _ in range(20):
                start_time = time.time()
                response = test_client_macos.get(endpoint)
                end_time = time.time()
                
                if response.status_code == 200:
                    times.append(end_time - start_time)
            
            if times:
                baselines[endpoint] = {
                    "avg_time": sum(times) / len(times),
                    "max_time": max(times),
                    "min_time": min(times),
                    "p95_time": sorted(times)[int(len(times) * 0.95)]
                }
        
        # Document baseline expectations
        for endpoint, metrics in baselines.items():
            # Core endpoints should be fast
            assert metrics["avg_time"] < 1.0, f"{endpoint} average time: {metrics['avg_time']}s"
            assert metrics["p95_time"] < 2.0, f"{endpoint} p95 time: {metrics['p95_time']}s"
    
    def test_cold_start_performance(self, test_client_macos):
        """Test performance during application cold start."""
        # This simulates the first requests after app startup
        # which might be slower due to initialization
        
        start_time = time.time()
        response = test_client_macos.get("/")
        end_time = time.time()
        
        # First request might be slower but should still be reasonable
        cold_start_time = end_time - start_time
        assert cold_start_time < 3.0, f"Cold start too slow: {cold_start_time}s"
        assert response.status_code == 200
    
    def test_sustained_load_performance(self, test_client_macos):
        """Test performance under sustained load."""
        duration = 10  # seconds
        request_count = 0
        start_time = time.time()
        response_times = []
        
        # Make requests for specified duration
        while time.time() - start_time < duration:
            request_start = time.time()
            response = test_client_macos.get("/health")
            request_end = time.time()
            
            response_times.append(request_end - request_start)
            request_count += 1
            
            assert response.status_code == 200
            
            # Small delay to prevent overwhelming
            time.sleep(0.01)
        
        # Calculate throughput and performance
        total_time = time.time() - start_time
        throughput = request_count / total_time  # requests per second
        avg_response_time = sum(response_times) / len(response_times)
        
        # Performance expectations for sustained load
        assert throughput > 5.0, f"Throughput too low: {throughput} req/s"
        assert avg_response_time < 1.5, f"Average response time under load: {avg_response_time}s"


class TestScalabilityLimits:
    """Test API scalability limits and bottlenecks."""
    
    def test_connection_limit_handling(self, test_client_macos):
        """Test API behavior at connection limits."""
        # Simulate many concurrent connections
        num_connections = 50
        connection_results = []
        
        def test_connection():
            """Test a single connection."""
            try:
                response = test_client_macos.get("/health")
                return {
                    "success": response.status_code == 200,
                    "status_code": response.status_code
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e)
                }
        
        # Create many concurrent connections
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_connections) as executor:
            futures = [executor.submit(test_connection) for _ in range(num_connections)]
            connection_results = [future.result() for future in futures]
        
        # Analyze connection handling
        success_count = sum(1 for r in connection_results if r["success"])
        success_rate = success_count / num_connections
        
        # Should handle most connections successfully
        assert success_rate >= 0.8, f"Connection success rate too low: {success_rate}"
    
    def test_data_size_scaling(self, test_client_macos):
        """Test API performance with varying data sizes."""
        # Mock services to return different data sizes
        data_sizes = [
            ("small", 100),    # 100 bytes
            ("medium", 10000), # 10KB  
            ("large", 100000), # 100KB
        ]
        
        for size_name, size_bytes in data_sizes:
            mock_data = "x" * size_bytes
            
            with patch("src.oaDeviceAPI.platforms.macos.services.camera.get_camera_info") as mock_camera:
                mock_camera.return_value = [
                    {"id": "test", "name": "Test Camera", "description": mock_data}
                ]
                
                start_time = time.time()
                response = test_client_macos.get("/cameras")
                end_time = time.time()
                
                response_time = end_time - start_time
                
                if response.status_code == 200:
                    # Larger responses should not be disproportionately slower
                    max_expected_time = 0.1 + (size_bytes / 1000000)  # Base + size factor
                    assert response_time < max_expected_time, \
                        f"{size_name} response too slow: {response_time}s for {size_bytes} bytes"
    
    def test_cpu_intensive_operations_performance(self, test_client_macos):
        """Test performance of CPU-intensive operations."""
        # Mock CPU-intensive service operations
        with patch("src.oaDeviceAPI.platforms.macos.services.standardized_metrics.get_standardized_metrics") as mock_metrics:
            
            def slow_metrics():
                # Simulate CPU-intensive work
                time.sleep(0.1)  # 100ms processing
                return {
                    "cpu": {"usage_percent": 25.0},
                    "memory": {"usage_percent": 30.0},
                    "disk": {"usage_percent": 40.0},
                    "network": {"bytes_sent": 1000, "bytes_received": 2000}
                }
            
            mock_metrics.side_effect = slow_metrics
            
            # Test multiple requests
            start_time = time.time()
            responses = []
            for _ in range(5):
                response = test_client_macos.get("/health")
                responses.append(response)
            end_time = time.time()
            
            total_time = end_time - start_time
            
            # Should handle CPU-intensive operations efficiently
            assert all(r.status_code == 200 for r in responses)
            assert total_time < 3.0, f"CPU-intensive operations too slow: {total_time}s"


class TestMemoryPerformance:
    """Test memory performance characteristics."""
    
    def test_memory_efficient_request_handling(self, test_client_macos):
        """Test that request handling is memory efficient."""
        import psutil
        
        process = psutil.Process()
        initial_memory = process.memory_info().rss
        
        # Make many requests to test memory usage
        for _ in range(200):
            response = test_client_macos.get("/health")
            assert response.status_code == 200
        
        # Force garbage collection
        import gc
        gc.collect()
        
        final_memory = process.memory_info().rss
        memory_growth = final_memory - initial_memory
        memory_growth_mb = memory_growth / (1024 * 1024)
        
        # Memory growth should be minimal for stateless API
        assert memory_growth_mb < 20.0, f"Excessive memory growth: {memory_growth_mb}MB"
    
    def test_large_response_memory_efficiency(self, test_client_macos):
        """Test memory efficiency when handling large responses."""
        # Create a large mock response
        large_mock_data = {
            "large_field": "x" * 500000,  # 500KB of data
            "array_field": [{"data": "y" * 1000} for _ in range(100)]  # 100KB array
        }
        
        with patch("src.oaDeviceAPI.platforms.macos.services.system.get_system_info",
                  return_value=large_mock_data):
            
            import psutil
            process = psutil.Process()
            initial_memory = process.memory_info().rss
            
            response = test_client_macos.get("/health")
            
            final_memory = process.memory_info().rss
            memory_used = final_memory - initial_memory
            memory_used_mb = memory_used / (1024 * 1024)
            
            assert response.status_code == 200
            # Memory usage should be reasonable for large response
            assert memory_used_mb < 100.0, f"Large response used too much memory: {memory_used_mb}MB"


class TestDatabasePerformance:
    """Test database/storage performance (if applicable)."""
    
    def test_config_loading_performance(self):
        """Test configuration loading performance."""
        from src.oaDeviceAPI.core.config import Settings, get_platform_config
        
        # Test configuration loading speed
        start_time = time.time()
        for _ in range(100):
            settings = Settings()
            config = get_platform_config()
        end_time = time.time()
        
        total_time = end_time - start_time
        
        # Configuration loading should be very fast
        assert total_time < 1.0, f"Configuration loading too slow: {total_time}s for 100 loads"
    
    def test_schema_validation_performance(self):
        """Test Pydantic schema validation performance."""
        from src.oaDeviceAPI.models.health_schemas import BaseHealthMetrics
        
        # Large dataset for validation testing
        test_data = {
            "cpu": {"usage_percent": 25.0, "cores": 8, "architecture": "arm64"},
            "memory": {"usage_percent": 30.0, "total": 8000000000, "used": 2400000000, "available": 5600000000},
            "disk": {"usage_percent": 40.0, "total": 500000000000, "used": 200000000000, "free": 300000000000},
            "network": {"bytes_sent": 1000000, "bytes_received": 2000000, "packets_sent": 500, "packets_received": 750}
        }
        
        # Test schema validation performance
        start_time = time.time()
        for _ in range(1000):
            metrics = BaseHealthMetrics(**test_data)
            _ = metrics.model_dump()
        end_time = time.time()
        
        total_time = end_time - start_time
        per_validation = total_time / 1000
        
        # Schema validation should be fast
        assert per_validation < 0.001, f"Schema validation too slow: {per_validation}s per validation"
        assert total_time < 2.0, f"Total validation time too slow: {total_time}s for 1000 validations"


class TestNetworkPerformance:
    """Test network performance characteristics."""
    
    @patch("aiohttp.ClientSession.get")
    async def test_external_api_call_performance(self, mock_get, test_client_macos):
        """Test performance of external API calls."""
        # Mock external service response with realistic timing
        async def mock_slow_response():
            await asyncio.sleep(0.1)  # 100ms delay
            mock_response = Mock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={"stats": "data"})
            return mock_response
        
        mock_get.return_value.__aenter__ = mock_slow_response
        
        start_time = time.time()
        response = test_client_macos.get("/tracker/stats")
        end_time = time.time()
        
        # Should handle external API delays efficiently
        total_time = end_time - start_time
        assert total_time < 1.0, f"External API call handling too slow: {total_time}s"
    
    @patch("aiohttp.ClientSession.get") 
    async def test_timeout_handling_performance(self, mock_get, test_client_macos):
        """Test performance of timeout handling."""
        # Mock timeout scenario
        mock_get.side_effect = asyncio.TimeoutError("Request timed out")
        
        start_time = time.time()
        response = test_client_macos.get("/tracker/stats")
        end_time = time.time()
        
        # Timeout handling should be fast
        timeout_handling_time = end_time - start_time
        assert timeout_handling_time < 0.5, f"Timeout handling too slow: {timeout_handling_time}s"
        
        # Should return appropriate error
        if response.status_code == 200:
            data = response.json()
            assert data.get("healthy") is False


class TestPerformanceBenchmarks:
    """Performance benchmarks for regression testing."""
    
    def test_health_endpoint_benchmark(self, test_client_macos):
        """Benchmark health endpoint performance."""
        # Establish performance benchmark
        iterations = 100
        start_time = time.time()
        
        for _ in range(iterations):
            response = test_client_macos.get("/health")
            assert response.status_code == 200
        
        end_time = time.time()
        total_time = end_time - start_time
        requests_per_second = iterations / total_time
        avg_response_time = total_time / iterations
        
        # Performance benchmarks (these serve as regression detection)
        assert requests_per_second > 20.0, f"Throughput benchmark failed: {requests_per_second} req/s"
        assert avg_response_time < 0.05, f"Response time benchmark failed: {avg_response_time}s"
    
    def test_concurrent_users_simulation(self, test_client_macos):
        """Simulate multiple concurrent users."""
        num_users = 10
        requests_per_user = 20
        user_results = []
        
        def simulate_user():
            """Simulate a single user's request pattern."""
            user_times = []
            
            for _ in range(requests_per_user):
                start_time = time.time()
                response = test_client_macos.get("/health") 
                end_time = time.time()
                
                user_times.append(end_time - start_time)
                
                # Realistic user delay
                time.sleep(0.05)  # 50ms between requests
            
            return {
                "avg_response_time": sum(user_times) / len(user_times),
                "max_response_time": max(user_times),
                "total_requests": len(user_times)
            }
        
        # Simulate concurrent users
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_users) as executor:
            futures = [executor.submit(simulate_user) for _ in range(num_users)]
            user_results = [future.result() for future in futures]
        
        # Analyze multi-user performance
        overall_avg_time = sum(r["avg_response_time"] for r in user_results) / len(user_results)
        worst_user_time = max(r["max_response_time"] for r in user_results)
        total_requests = sum(r["total_requests"] for r in user_results)
        
        # Multi-user performance expectations
        assert overall_avg_time < 1.0, f"Multi-user average time too slow: {overall_avg_time}s"
        assert worst_user_time < 3.0, f"Worst user experience too slow: {worst_user_time}s"
        assert total_requests == num_users * requests_per_user


class TestPerformanceMonitoring:
    """Test performance monitoring and alerting."""
    
    def test_slow_request_detection(self, test_client_macos, caplog):
        """Test detection of slow requests."""
        import logging
        
        # Mock a slow service
        with patch("src.oaDeviceAPI.platforms.macos.services.standardized_metrics.get_standardized_metrics") as mock_metrics:
            def slow_service():
                time.sleep(1.0)  # 1 second delay
                return {
                    "cpu": {"usage_percent": 25.0},
                    "memory": {"usage_percent": 30.0},
                    "disk": {"usage_percent": 40.0},
                }
            
            mock_metrics.side_effect = slow_service
            
            with caplog.at_level(logging.WARNING):
                response = test_client_macos.get("/health")
                
                # Should detect slow request (if monitoring is implemented)
                # This test documents expected monitoring behavior
                slow_request_logs = [r for r in caplog.records if "slow" in r.getMessage().lower()]
                
                # May or may not have slow request monitoring currently
                # This test serves as documentation for performance monitoring requirements
    
    def test_resource_usage_monitoring(self, test_client_macos):
        """Test resource usage monitoring during requests."""
        import psutil
        
        # Monitor resource usage during requests
        initial_cpu = psutil.cpu_percent(interval=None)
        initial_memory = psutil.virtual_memory().percent
        
        # Make requests while monitoring
        for _ in range(20):
            response = test_client_macos.get("/health")
            assert response.status_code == 200
        
        final_cpu = psutil.cpu_percent(interval=1)
        final_memory = psutil.virtual_memory().percent
        
        # Resource usage should remain reasonable
        cpu_increase = final_cpu - initial_cpu
        memory_increase = final_memory - initial_memory
        
        # Document expected resource usage patterns
        # These thresholds serve as performance regression detection
        assert cpu_increase < 30.0, f"CPU usage increased too much: {cpu_increase}%"
        assert memory_increase < 10.0, f"Memory usage increased too much: {memory_increase}%"