"""Integration tests for cross-platform compatibility and consistency."""

import pytest
from unittest.mock import patch, Mock
from fastapi import status
import json


class TestCrossPlatformAPIs:
    """Test API consistency across platforms."""
    
    def test_health_endpoint_schema_consistency(self, test_client_macos, test_client_orangepi):
        """Test that health endpoints return consistent schemas across platforms."""
        macos_response = test_client_macos.get("/health")
        orangepi_response = test_client_orangepi.get("/health")
        
        # Both should succeed
        assert macos_response.status_code == 200
        assert orangepi_response.status_code == 200
        
        macos_data = macos_response.json()
        orangepi_data = orangepi_response.json()
        
        # Core schema should be identical
        core_fields = ["status", "hostname", "timestamp", "timestamp_epoch", "version", "metrics", "device_info"]
        for field in core_fields:
            assert field in macos_data, f"macOS missing field: {field}"
            assert field in orangepi_data, f"OrangePi missing field: {field}"
        
        # Metrics structure should be consistent
        metrics_fields = ["cpu", "memory", "disk", "network"]
        for field in metrics_fields:
            assert field in macos_data["metrics"], f"macOS metrics missing: {field}"
            assert field in orangepi_data["metrics"], f"OrangePi metrics missing: {field}"
            
            # Metric subfields should be consistent
            if field == "cpu":
                cpu_fields = ["usage_percent", "cores"]
                for cpu_field in cpu_fields:
                    assert cpu_field in macos_data["metrics"]["cpu"], f"macOS CPU missing: {cpu_field}"
                    assert cpu_field in orangepi_data["metrics"]["cpu"], f"OrangePi CPU missing: {cpu_field}"
    
    def test_platform_endpoint_consistency(self, test_client_macos, test_client_orangepi):
        """Test platform endpoint returns consistent structure."""
        macos_response = test_client_macos.get("/platform")
        orangepi_response = test_client_orangepi.get("/platform")
        
        assert macos_response.status_code == 200
        assert orangepi_response.status_code == 200
        
        macos_data = macos_response.json()
        orangepi_data = orangepi_response.json()
        
        # Structure should be consistent
        required_fields = ["platform", "service_manager", "features"]
        for field in required_fields:
            assert field in macos_data
            assert field in orangepi_data
        
        # Platform values should be different but valid
        assert macos_data["platform"] == "macos"
        assert orangepi_data["platform"] == "orangepi"
        
        # Features should have same keys but different values
        macos_features = set(macos_data["features"].keys())
        orangepi_features = set(orangepi_data["features"].keys())
        assert macos_features == orangepi_features  # Same feature keys
    
    def test_error_response_consistency(self, test_client_macos, test_client_orangepi):
        """Test that error responses are consistent across platforms."""
        error_endpoints = [
            "/nonexistent",
            "/health/invalid",
            "/platform/unknown"
        ]
        
        for endpoint in error_endpoints:
            macos_response = test_client_macos.get(endpoint)
            orangepi_response = test_client_orangepi.get(endpoint)
            
            # Error status codes should be consistent
            assert macos_response.status_code == orangepi_response.status_code
            
            # Error response structure should be consistent
            if macos_response.headers.get("content-type", "").startswith("application/json"):
                macos_error = macos_response.json()
                orangepi_error = orangepi_response.json()
                
                # Should have same error structure
                assert type(macos_error) == type(orangepi_error)
                
                if isinstance(macos_error, dict):
                    # Both should have error details
                    error_fields = ["detail", "message", "error"]
                    macos_has_error = any(field in macos_error for field in error_fields)
                    orangepi_has_error = any(field in orangepi_error for field in error_fields)
                    assert macos_has_error == orangepi_has_error


class TestPlatformSpecificFeatures:
    """Test platform-specific features work correctly."""
    
    def test_macos_specific_endpoints(self, test_client_macos):
        """Test macOS-specific endpoints are available and functional.""" 
        # Test camera endpoints (macOS only)
        camera_response = test_client_macos.get("/cameras")
        
        # Should either work or indicate feature availability
        assert camera_response.status_code in [200, 404, 503]
        
        if camera_response.status_code == 200:
            camera_data = camera_response.json()
            assert "cameras" in camera_data or "count" in camera_data
        
        # Test tracker endpoints (macOS only)
        tracker_response = test_client_macos.get("/tracker/stats")
        assert tracker_response.status_code in [200, 404, 503]
        
        # Test camguard endpoints (macOS only)
        camguard_response = test_client_macos.get("/camguard/status")
        assert camguard_response.status_code in [200, 404, 503]
    
    def test_orangepi_specific_endpoints(self, test_client_orangepi):
        """Test OrangePi-specific endpoints are available and functional."""
        # Test screenshot endpoints (OrangePi only)
        screenshot_response = test_client_orangepi.post("/screenshots/capture")
        
        # Should either work or indicate feature availability
        assert screenshot_response.status_code in [200, 400, 404, 503]
        
        if screenshot_response.status_code == 200:
            screenshot_data = screenshot_response.json()
            assert "success" in screenshot_data or "file_path" in screenshot_data
        
        # Test screenshot history
        history_response = test_client_orangepi.get("/screenshots/history")
        assert history_response.status_code in [200, 404, 503]
    
    def test_platform_feature_isolation(self, test_client_macos, test_client_orangepi):
        """Test that platform-specific features are properly isolated."""
        # macOS should not have screenshot endpoints
        macos_screenshot_response = test_client_macos.post("/screenshots/capture")
        assert macos_screenshot_response.status_code == 404  # Not found
        
        # OrangePi should not have camera endpoints
        orangepi_camera_response = test_client_orangepi.get("/cameras")
        assert orangepi_camera_response.status_code == 404  # Not found
        
        # OrangePi should not have tracker endpoints
        orangepi_tracker_response = test_client_orangepi.get("/tracker/stats")
        assert orangepi_tracker_response.status_code == 404  # Not found
    
    def test_action_endpoint_platform_differences(self, test_client_macos, test_client_orangepi):
        """Test that action endpoints differ appropriately by platform."""
        # Get available actions from root endpoint
        macos_root = test_client_macos.get("/").json()
        orangepi_root = test_client_orangepi.get("/").json()
        
        macos_actions = macos_root.get("endpoints", {}).get("actions", {})
        orangepi_actions = orangepi_root.get("endpoints", {}).get("actions", {})
        
        # Both should have reboot
        assert "reboot" in macos_actions
        assert "reboot" in orangepi_actions
        
        # Platform-specific actions
        assert "restart_tracker" in macos_actions
        assert "restart_tracker" not in orangepi_actions
        
        assert "restart_player" in orangepi_actions
        assert "restart_player" not in macos_actions


class TestDataFormatCompatibility:
    """Test data format compatibility across platforms."""
    
    def test_timestamp_format_consistency(self, test_client_macos, test_client_orangepi):
        """Test that timestamps are formatted consistently."""
        macos_health = test_client_macos.get("/health").json()
        orangepi_health = test_client_orangepi.get("/health").json()
        
        # Both should have timestamps
        assert "timestamp" in macos_health
        assert "timestamp" in orangepi_health
        assert "timestamp_epoch" in macos_health 
        assert "timestamp_epoch" in orangepi_health
        
        # ISO format check
        macos_timestamp = macos_health["timestamp"]
        orangepi_timestamp = orangepi_health["timestamp"]
        
        # Should be valid ISO format (basic validation)
        assert "T" in macos_timestamp or " " in macos_timestamp
        assert "T" in orangepi_timestamp or " " in orangepi_timestamp
        
        # Epoch timestamps should be integers
        assert isinstance(macos_health["timestamp_epoch"], int)
        assert isinstance(orangepi_health["timestamp_epoch"], int)
    
    def test_numeric_precision_consistency(self, test_client_macos, test_client_orangepi):
        """Test that numeric values have consistent precision."""
        macos_health = test_client_macos.get("/health").json()
        orangepi_health = test_client_orangepi.get("/health").json()
        
        # Check CPU usage precision
        macos_cpu = macos_health["metrics"]["cpu"]["usage_percent"]
        orangepi_cpu = orangepi_health["metrics"]["cpu"]["usage_percent"]
        
        # Should be float values with reasonable precision
        assert isinstance(macos_cpu, (int, float))
        assert isinstance(orangepi_cpu, (int, float))
        
        # Precision should be reasonable (not excessive decimal places)
        if isinstance(macos_cpu, float):
            assert len(str(macos_cpu).split(".")[-1]) <= 2  # Max 2 decimal places
        if isinstance(orangepi_cpu, float):
            assert len(str(orangepi_cpu).split(".")[-1]) <= 2
    
    def test_boolean_value_consistency(self, test_client_macos, test_client_orangepi):
        """Test that boolean values are consistent."""
        macos_platform = test_client_macos.get("/platform").json()
        orangepi_platform = test_client_orangepi.get("/platform").json()
        
        # Feature flags should be boolean
        for platform_data in [macos_platform, orangepi_platform]:
            features = platform_data.get("features", {})
            for feature_name, feature_value in features.items():
                assert isinstance(feature_value, bool), \
                    f"Feature {feature_name} should be boolean, got {type(feature_value)}"


class TestPlatformMigrationCompatibility:
    """Test compatibility for platform migration scenarios.""" 
    
    def test_health_data_portability(self, test_client_macos, test_client_orangepi):
        """Test that health data can be compared across platforms."""
        macos_health = test_client_macos.get("/health").json()
        orangepi_health = test_client_orangepi.get("/health").json()
        
        # Core metrics should be comparable
        comparable_fields = ["cpu.usage_percent", "memory.usage_percent", "disk.usage_percent"]
        
        for field_path in comparable_fields:
            field_parts = field_path.split(".")
            
            # Extract nested values
            macos_value = macos_health["metrics"]
            orangepi_value = orangepi_health["metrics"]
            
            for part in field_parts:
                macos_value = macos_value[part]
                orangepi_value = orangepi_value[part]
            
            # Values should be in same range and format
            assert isinstance(macos_value, type(orangepi_value))
            assert 0 <= macos_value <= 100  # Percentage values
            assert 0 <= orangepi_value <= 100
    
    def test_configuration_portability(self):
        """Test that configuration can be shared across platforms."""
        from src.oaDeviceAPI.core.config import Settings
        
        # Test with shared environment variables
        shared_config = {
            "OAAPI_HOST": "0.0.0.0",
            "OAAPI_PORT": "9090", 
            "LOG_LEVEL": "INFO",
            "TAILSCALE_SUBNET": "100.64.0.0/10"
        }
        
        with patch.dict("os.environ", shared_config):
            # Both platforms should handle same config
            with patch("src.oaDeviceAPI.core.config.DETECTED_PLATFORM", "macos"):
                macos_settings = Settings()
            
            with patch("src.oaDeviceAPI.core.config.DETECTED_PLATFORM", "orangepi"):
                orangepi_settings = Settings()
            
            # Shared settings should be identical
            assert macos_settings.host == orangepi_settings.host
            assert macos_settings.port == orangepi_settings.port
            assert macos_settings.log_level == orangepi_settings.log_level
            assert macos_settings.tailscale_subnet == orangepi_settings.tailscale_subnet
    
    def test_api_client_compatibility(self, test_client_macos, test_client_orangepi):
        """Test that API clients can work with both platforms."""
        # Simulate client code that works with both platforms
        
        def generic_health_check(client):
            """Generic health check that should work on any platform."""
            response = client.get("/health")
            assert response.status_code == 200
            
            data = response.json()
            
            # Client should be able to rely on these fields existing
            required_fields = ["status", "metrics", "timestamp"]
            for field in required_fields:
                assert field in data
            
            return data
        
        # Test with both clients
        macos_health = generic_health_check(test_client_macos)
        orangepi_health = generic_health_check(test_client_orangepi)
        
        # Client should get consistent data structure
        assert type(macos_health) == type(orangepi_health)
        assert set(macos_health.keys()) & set(orangepi_health.keys())  # Common fields


class TestFeatureDetectionConsistency:
    """Test feature detection consistency across platforms."""
    
    def test_feature_matrix_completeness(self, test_client_macos, test_client_orangepi):
        """Test that feature matrices are complete and consistent."""
        macos_root = test_client_macos.get("/").json()
        orangepi_root = test_client_orangepi.get("/").json()
        
        macos_endpoints = macos_root["endpoints"]
        orangepi_endpoints = orangepi_root["endpoints"]
        
        # Core endpoints should exist on both
        core_endpoints = ["health", "platform", "actions"]
        for endpoint in core_endpoints:
            assert endpoint in macos_endpoints
            assert endpoint in orangepi_endpoints
        
        # Platform-specific endpoints should be correctly differentiated
        assert "cameras" in macos_endpoints
        assert "cameras" not in orangepi_endpoints
        
        assert "screenshots" in orangepi_endpoints  
        assert "screenshots" not in macos_endpoints
        
        assert "tracker" in macos_endpoints
        assert "tracker" not in orangepi_endpoints
    
    def test_feature_flag_consistency(self, test_client_macos, test_client_orangepi):
        """Test that feature flags are consistent with available endpoints."""
        macos_platform = test_client_macos.get("/platform").json()
        orangepi_platform = test_client_orangepi.get("/platform").json()
        
        macos_features = macos_platform["features"]
        orangepi_features = orangepi_platform["features"]
        
        # Feature flags should match endpoint availability
        # macOS should support camera and tracker
        assert macos_features["camera"] is True
        assert macos_features["tracker"] is True
        assert macos_features["screenshot"] is False
        
        # OrangePi should support screenshots but not camera/tracker
        assert orangepi_features["screenshot"] is True
        assert orangepi_features["camera"] is False
        assert orangepi_features["tracker"] is False
    
    def test_capability_reporting_accuracy(self, test_client_macos, test_client_orangepi):
        """Test that reported capabilities match actual functionality."""
        # Test macOS capabilities
        macos_health = test_client_macos.get("/health").json()
        macos_capabilities = macos_health.get("capabilities", {})
        
        if "supports_camera_stream" in macos_capabilities and macos_capabilities["supports_camera_stream"]:
            # Should have camera endpoints available
            camera_response = test_client_macos.get("/cameras")
            assert camera_response.status_code in [200, 503]  # Available or temporarily unavailable
        
        # Test OrangePi capabilities
        orangepi_health = test_client_orangepi.get("/health").json()
        orangepi_capabilities = orangepi_health.get("capabilities", {})
        
        if "supports_screenshots" in orangepi_capabilities and orangepi_capabilities["supports_screenshots"]:
            # Should have screenshot endpoints available
            screenshot_response = test_client_orangepi.post("/screenshots/capture")
            assert screenshot_response.status_code in [200, 400, 503]  # Available or error


class TestVersionCompatibility:
    """Test version compatibility across platforms."""
    
    def test_api_version_consistency(self, test_client_macos, test_client_orangepi):
        """Test that API versions are consistent across platforms."""
        macos_root = test_client_macos.get("/").json()
        orangepi_root = test_client_orangepi.get("/").json()
        
        # API version should be identical
        assert macos_root["version"] == orangepi_root["version"]
        
        # Health endpoint version info should be consistent
        macos_health = test_client_macos.get("/health").json()
        orangepi_health = test_client_orangepi.get("/health").json()
        
        macos_version = macos_health["version"]["api"]
        orangepi_version = orangepi_health["version"]["api"]
        
        assert macos_version == orangepi_version
    
    def test_schema_version_compatibility(self, test_client_macos, test_client_orangepi):
        """Test that schema versions are compatible."""
        # Both platforms should use compatible schema versions
        macos_health = test_client_macos.get("/health").json()
        orangepi_health = test_client_orangepi.get("/health").json()
        
        # Schema structure should be compatible
        def get_schema_signature(data):
            """Get a signature of the data schema."""
            if isinstance(data, dict):
                return {key: get_schema_signature(value) for key, value in data.items()}
            elif isinstance(data, list) and data:
                return [get_schema_signature(data[0])]
            else:
                return type(data).__name__
        
        macos_signature = get_schema_signature(macos_health)
        orangepi_signature = get_schema_signature(orangepi_health)
        
        # Core structure should be compatible
        core_fields = ["status", "timestamp", "metrics", "device_info"]
        for field in core_fields:
            if field in macos_signature and field in orangepi_signature:
                # Field types should be compatible
                assert type(macos_signature[field]) == type(orangepi_signature[field])


class TestMigrationScenarios:
    """Test scenarios relevant to platform migration."""
    
    def test_health_data_migration_compatibility(self, test_client_macos, test_client_orangepi):
        """Test that health data can be migrated between platforms."""
        macos_health = test_client_macos.get("/health").json()
        orangepi_health = test_client_orangepi.get("/health").json()
        
        # Extract portable data (metrics that exist on both)
        portable_fields = ["cpu", "memory", "disk", "network"]
        
        for field in portable_fields:
            macos_metric = macos_health["metrics"][field]
            orangepi_metric = orangepi_health["metrics"][field]
            
            # Should have compatible structure for migration
            common_subfields = set(macos_metric.keys()) & set(orangepi_metric.keys())
            assert len(common_subfields) > 0, f"No common subfields in {field} metrics"
            
            # Common subfields should have compatible types
            for subfield in common_subfields:
                macos_type = type(macos_metric[subfield])
                orangepi_type = type(orangepi_metric[subfield])
                assert macos_type == orangepi_type, \
                    f"Incompatible types for {field}.{subfield}: {macos_type} vs {orangepi_type}"
    
    def test_configuration_migration_compatibility(self):
        """Test configuration migration compatibility."""
        from src.oaDeviceAPI.core.config import PLATFORM_CONFIG
        
        # Test that configurations have overlapping structure
        macos_config = PLATFORM_CONFIG["macos"]
        orangepi_config = PLATFORM_CONFIG["orangepi"]
        
        # Core config keys should exist in both
        core_config_keys = ["service_manager", "temp_dir", "bin_paths"]
        
        for key in core_config_keys:
            assert key in macos_config, f"macOS config missing: {key}"
            assert key in orangepi_config, f"OrangePi config missing: {key}"
            
            # Types should be compatible
            assert type(macos_config[key]) == type(orangepi_config[key])


class TestBackwardCompatibility:
    """Test backward compatibility considerations."""
    
    def test_deprecated_endpoint_handling(self, test_client_macos):
        """Test handling of deprecated endpoints (if any)."""
        # Test potential legacy endpoints
        legacy_endpoints = [
            "/status",  # Might be old health endpoint
            "/info",    # Might be old platform endpoint
            "/metrics", # Might be old metrics endpoint
        ]
        
        for endpoint in legacy_endpoints:
            response = test_client_macos.get(endpoint)
            
            # Should either redirect, return compatibility response, or 404
            assert response.status_code in [200, 301, 302, 404, 410]  # 410 = Gone
            
            if response.status_code in [301, 302]:
                # Should redirect to new endpoint
                assert "location" in response.headers
    
    def test_api_version_header_support(self, test_client_macos):
        """Test support for API version headers."""
        # Test with version headers
        version_headers = [
            {"Accept": "application/vnd.orangead.v1+json"},
            {"API-Version": "1.0"},
            {"X-API-Version": "1.0.0"}
        ]
        
        for headers in version_headers:
            response = test_client_macos.get("/health", headers=headers)
            
            # Should handle version headers gracefully
            assert response.status_code in [200, 400, 406]  # 406 = Not Acceptable
    
    def test_legacy_field_support(self, test_client_macos, test_client_orangepi):
        """Test support for legacy field names in responses."""
        # Check if responses include legacy field names for backward compatibility
        macos_health = test_client_macos.get("/health").json()
        orangepi_health = test_client_orangepi.get("/health").json()
        
        # Example: Both old and new field names might be present
        legacy_mappings = [
            ("cpu_usage", "cpu.usage_percent"),
            ("memory_usage", "memory.usage_percent"),
            ("hostname", "device_info.hostname")
        ]
        
        for legacy_field, new_field_path in legacy_mappings:
            # Extract new field value
            field_parts = new_field_path.split(".")
            macos_value = macos_health
            orangepi_value = orangepi_health
            
            try:
                for part in field_parts:
                    macos_value = macos_value[part]
                    orangepi_value = orangepi_value[part]
                
                # If legacy field exists, should match new field
                if legacy_field in macos_health:
                    assert macos_health[legacy_field] == macos_value
                if legacy_field in orangepi_health:
                    assert orangepi_health[legacy_field] == orangepi_value
                    
            except KeyError:
                # New field path might not exist, which is okay
                pass


class TestCrossPlatformIntegrationScenarios:
    """Test real-world cross-platform integration scenarios."""
    
    def test_dashboard_integration_compatibility(self, test_client_macos, test_client_orangepi):
        """Test compatibility for oaDashboard integration."""
        # Test the data format expected by oaDashboard
        
        # Both platforms should provide dashboard-compatible data
        endpoints_for_dashboard = ["/health", "/platform"]
        
        for endpoint in endpoints_for_dashboard:
            macos_response = test_client_macos.get(endpoint)
            orangepi_response = test_client_orangepi.get(endpoint)
            
            assert macos_response.status_code == 200
            assert orangepi_response.status_code == 200
            
            macos_data = macos_response.json()
            orangepi_data = orangepi_response.json()
            
            # Dashboard should be able to process both responses with same code
            # This means having consistent required fields
            if endpoint == "/health":
                dashboard_required_fields = [
                    "status", "hostname", "timestamp", "metrics"
                ]
                
                for field in dashboard_required_fields:
                    assert field in macos_data, f"Dashboard field missing from macOS: {field}"
                    assert field in orangepi_data, f"Dashboard field missing from OrangePi: {field}"
    
    def test_ansible_deployment_compatibility(self, test_client_macos, test_client_orangepi):
        """Test compatibility for oaAnsible deployment."""
        # Test endpoints that oaAnsible might use for health checks
        deployment_endpoints = ["/", "/health", "/platform"]
        
        for endpoint in deployment_endpoints:
            for client, platform_name in [(test_client_macos, "macOS"), (test_client_orangepi, "OrangePi")]:
                response = client.get(endpoint)
                
                # Deployment health checks should work on both platforms
                assert response.status_code == 200, \
                    f"Deployment health check failed for {platform_name} on {endpoint}"
                
                data = response.json()
                
                # Should provide deployment-relevant information
                if endpoint == "/":
                    assert "status" in data
                    assert data["status"] == "running"
                elif endpoint == "/platform":
                    assert "platform" in data
                    assert data["platform"] in ["macos", "orangepi"]
    
    def test_monitoring_system_compatibility(self, test_client_macos, test_client_orangepi):
        """Test compatibility for external monitoring systems."""
        # External monitoring should be able to monitor both platforms uniformly
        
        monitoring_endpoints = ["/health", "/health/summary"]
        
        for endpoint in monitoring_endpoints:
            macos_response = test_client_macos.get(endpoint)
            orangepi_response = test_client_orangepi.get(endpoint)
            
            # Monitoring endpoints should work on both platforms
            if macos_response.status_code == 200 and orangepi_response.status_code == 200:
                macos_data = macos_response.json()
                orangepi_data = orangepi_response.json()
                
                # Monitoring system should get consistent alerting data
                monitoring_fields = ["status", "timestamp"]
                for field in monitoring_fields:
                    if field in macos_data and field in orangepi_data:
                        # Field types should be consistent for monitoring
                        assert type(macos_data[field]) == type(orangepi_data[field])
    
    def test_load_balancer_compatibility(self, test_client_macos, test_client_orangepi):
        """Test compatibility for load balancer health checks."""
        # Load balancers typically use simple health checks
        health_check_endpoints = ["/", "/health"]
        
        for endpoint in health_check_endpoints:
            macos_response = test_client_macos.get(endpoint)
            orangepi_response = test_client_orangepi.get(endpoint)
            
            # Both should return 200 for healthy instances
            assert macos_response.status_code == 200
            assert orangepi_response.status_code == 200
            
            # Response time should be reasonable for health checks
            # (This is simulated since TestClient doesn't have real network timing)
            assert len(macos_response.content) < 100000  # Response not too large
            assert len(orangepi_response.content) < 100000


class TestDataTransformationCompatibility:
    """Test data transformation compatibility between platforms."""
    
    def test_unit_conversion_consistency(self, test_client_macos, test_client_orangepi):
        """Test that units are consistent across platforms."""
        macos_health = test_client_macos.get("/health").json()
        orangepi_health = test_client_orangepi.get("/health").json()
        
        # Memory should be in same units (bytes)
        macos_memory = macos_health["metrics"]["memory"]
        orangepi_memory = orangepi_health["metrics"]["memory"]
        
        # All memory values should be in bytes (large numbers)
        memory_fields = ["total", "used", "available"]
        for field in memory_fields:
            if field in macos_memory:
                assert macos_memory[field] > 1000000, f"macOS {field} not in bytes: {macos_memory[field]}"
            if field in orangepi_memory:
                assert orangepi_memory[field] > 1000000, f"OrangePi {field} not in bytes: {orangepi_memory[field]}"
        
        # Percentages should be 0-100
        percentage_fields = ["usage_percent"]
        for field in percentage_fields:
            if field in macos_memory:
                assert 0 <= macos_memory[field] <= 100
            if field in orangepi_memory:
                assert 0 <= orangepi_memory[field] <= 100
    
    def test_timezone_handling_consistency(self, test_client_macos, test_client_orangepi):
        """Test that timezone handling is consistent."""
        macos_health = test_client_macos.get("/health").json()
        orangepi_health = test_client_orangepi.get("/health").json()
        
        macos_timestamp = macos_health["timestamp"]
        orangepi_timestamp = orangepi_health["timestamp"]
        
        # Both should include timezone information or use UTC consistently
        # Check for timezone indicators
        timezone_indicators = ["Z", "+", "-", "UTC"]
        
        macos_has_tz = any(indicator in macos_timestamp for indicator in timezone_indicators)
        orangepi_has_tz = any(indicator in orangepi_timestamp for indicator in timezone_indicators)
        
        # Timezone handling should be consistent
        assert macos_has_tz == orangepi_has_tz, "Inconsistent timezone handling"
    
    def test_encoding_consistency(self, test_client_macos, test_client_orangepi):
        """Test that text encoding is consistent across platforms."""
        # Test with unicode data
        test_hostnames = ["测试设备", "café-machine", "naïve-system"]
        
        for hostname in test_hostnames:
            with patch("socket.gethostname", return_value=hostname):
                macos_response = test_client_macos.get("/health")
                orangepi_response = test_client_orangepi.get("/health")
                
                # Both should handle unicode consistently
                if macos_response.status_code == 200 and orangepi_response.status_code == 200:
                    macos_data = macos_response.json()
                    orangepi_data = orangepi_response.json()
                    
                    # Unicode should be preserved correctly
                    assert macos_data["hostname"] == hostname
                    assert orangepi_data["hostname"] == hostname


class TestFailoverCompatibility:
    """Test failover compatibility between platforms."""
    
    def test_graceful_degradation_consistency(self, test_client_macos, test_client_orangepi):
        """Test that graceful degradation works consistently."""
        # Simulate service failures on both platforms
        with patch("psutil.cpu_percent", side_effect=Exception("CPU monitoring failed")):
            macos_response = test_client_macos.get("/health")
            orangepi_response = test_client_orangepi.get("/health")
            
            # Both should degrade gracefully in same way
            if macos_response.status_code == 200 and orangepi_response.status_code == 200:
                macos_data = macos_response.json()
                orangepi_data = orangepi_response.json()
                
                # Both should indicate service issues consistently
                # Either both have error fields or both have fallback values
                macos_has_error = "error" in str(macos_data).lower()
                orangepi_has_error = "error" in str(orangepi_data).lower()
                
                # Error handling should be consistent
                assert macos_has_error == orangepi_has_error
    
    def test_fallback_mechanism_consistency(self, test_client_macos, test_client_orangepi):
        """Test that fallback mechanisms are consistent."""
        # Test with missing service dependencies
        with patch("subprocess.run", side_effect=FileNotFoundError("Service command not found")):
            macos_response = test_client_macos.get("/health")
            orangepi_response = test_client_orangepi.get("/health")
            
            # Both should handle missing dependencies consistently
            assert macos_response.status_code == orangepi_response.status_code
            
            if macos_response.status_code == 200 and orangepi_response.status_code == 200:
                macos_data = macos_response.json()
                orangepi_data = orangepi_response.json()
                
                # Fallback data structure should be consistent
                assert type(macos_data) == type(orangepi_data)
                
                # Core fields should still exist in fallback mode
                fallback_fields = ["status", "timestamp", "hostname"]
                for field in fallback_fields:
                    macos_has_field = field in macos_data
                    orangepi_has_field = field in orangepi_data
                    assert macos_has_field == orangepi_has_field


class TestClientLibraryCompatibility:
    """Test compatibility for client libraries."""
    
    def test_http_client_compatibility(self, test_client_macos, test_client_orangepi):
        """Test that standard HTTP clients work with both platforms."""
        # Simulate different HTTP client behaviors
        
        # Test with different Accept headers
        accept_headers = [
            {"Accept": "application/json"},
            {"Accept": "application/json, */*"},
            {"Accept": "*/*"},
            {}  # No Accept header
        ]
        
        for headers in accept_headers:
            macos_response = test_client_macos.get("/health", headers=headers)
            orangepi_response = test_client_orangepi.get("/health", headers=headers)
            
            # Both should handle different Accept headers consistently
            assert macos_response.status_code == orangepi_response.status_code
            
            if macos_response.status_code == 200:
                # Content type should be JSON regardless of Accept header
                assert "application/json" in macos_response.headers["content-type"]
                assert "application/json" in orangepi_response.headers["content-type"]
    
    def test_user_agent_compatibility(self, test_client_macos, test_client_orangepi):
        """Test compatibility with different User-Agent strings."""
        user_agents = [
            "Mozilla/5.0 (Browser)",
            "curl/7.68.0",
            "Python-requests/2.25.1",
            "oaDashboard/1.0.0",
            "Ansible/2.9.0"
        ]
        
        for user_agent in user_agents:
            headers = {"User-Agent": user_agent}
            
            macos_response = test_client_macos.get("/health", headers=headers)
            orangepi_response = test_client_orangepi.get("/health", headers=headers)
            
            # Should work with all user agents
            assert macos_response.status_code == 200
            assert orangepi_response.status_code == 200