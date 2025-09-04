"""Unit tests for middleware functionality."""

import ipaddress
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException, Request
from starlette.responses import Response

from src.oaDeviceAPI.middleware import TailscaleSubnetMiddleware


class TestTailscaleSubnetMiddleware:
    """Test TailscaleSubnetMiddleware functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_app = Mock()
        self.middleware = TailscaleSubnetMiddleware(
            app=self.mock_app,
            tailscale_subnet_str="100.64.0.0/10"
        )

    @pytest.mark.asyncio
    async def test_localhost_allowed(self):
        """Test that localhost connections are allowed."""
        call_next = AsyncMock(return_value=Response(content="OK"))

        localhost_ips = ["127.0.0.1", "::1", "localhost"]

        for ip in localhost_ips:
            request = Mock(spec=Request)
            request.client.host = ip

            response = await self.middleware.dispatch(request, call_next)

            assert response.status_code == 200
            call_next.assert_called_with(request)
            call_next.reset_mock()

    @pytest.mark.asyncio
    async def test_tailscale_ip_allowed(self):
        """Test that Tailscale subnet IPs are allowed."""
        call_next = AsyncMock(return_value=Response(content="OK"))

        # Valid Tailscale IPs
        tailscale_ips = [
            "100.64.0.1",
            "100.127.255.254",
            "100.100.100.100"
        ]

        for ip in tailscale_ips:
            request = Mock(spec=Request)
            request.client.host = ip

            response = await self.middleware.dispatch(request, call_next)

            assert response.status_code == 200
            call_next.assert_called_with(request)
            call_next.reset_mock()

    @pytest.mark.asyncio
    async def test_external_ip_blocked(self):
        """Test that external IPs are blocked."""
        call_next = AsyncMock()

        # External IPs that should be blocked
        external_ips = [
            "8.8.8.8",
            "1.1.1.1",
            "192.168.1.100",
            "10.0.0.1",
            "172.16.0.1"
        ]

        for ip in external_ips:
            request = Mock(spec=Request)
            request.client.host = ip

            with pytest.raises(HTTPException) as exc_info:
                await self.middleware.dispatch(request, call_next)

            assert exc_info.value.status_code == 403
            assert "Access denied" in exc_info.value.detail
            assert "Tailscale" in exc_info.value.detail
            call_next.assert_not_called()
            call_next.reset_mock()

    @pytest.mark.asyncio
    async def test_invalid_ip_format(self):
        """Test handling of invalid IP address formats."""
        call_next = AsyncMock()

        invalid_ips = [
            "not.an.ip",
            "256.256.256.256",
            "192.168.1",
            "192.168.1.1.1",
            "",
            "null"
        ]

        for ip in invalid_ips:
            request = Mock(spec=Request)
            request.client.host = ip

            with pytest.raises(HTTPException) as exc_info:
                await self.middleware.dispatch(request, call_next)

            assert exc_info.value.status_code == 400
            assert "Invalid client IP" in exc_info.value.detail
            call_next.assert_not_called()
            call_next.reset_mock()

    @pytest.mark.asyncio
    async def test_ipv6_support(self):
        """Test IPv6 address support."""
        # Create middleware with IPv6 Tailscale range
        ipv6_middleware = TailscaleSubnetMiddleware(
            app=self.mock_app,
            tailscale_subnet_str="fd7a:115c:a1e0::/48"
        )

        call_next = AsyncMock(return_value=Response(content="OK"))

        # Valid IPv6 Tailscale address
        request = Mock(spec=Request)
        request.client.host = "fd7a:115c:a1e0::1"

        response = await ipv6_middleware.dispatch(request, call_next)
        assert response.status_code == 200

        # Invalid IPv6 address
        request.client.host = "2001:db8::1"

        with pytest.raises(HTTPException) as exc_info:
            await ipv6_middleware.dispatch(request, call_next)
        assert exc_info.value.status_code == 403

    def test_middleware_initialization(self):
        """Test middleware initialization with different subnets."""
        # Test different valid subnet formats
        valid_subnets = [
            "100.64.0.0/10",
            "10.0.0.0/8",
            "192.168.0.0/16",
            "172.16.0.0/12"
        ]

        for subnet in valid_subnets:
            middleware = TailscaleSubnetMiddleware(
                app=self.mock_app,
                tailscale_subnet_str=subnet
            )
            assert isinstance(middleware.tailscale_subnet, ipaddress.IPv4Network)

    def test_middleware_invalid_subnet(self):
        """Test middleware with invalid subnet configuration."""
        invalid_subnets = [
            "invalid.subnet",
            "256.256.256.256/24",
            "192.168.1.1/33",  # Invalid CIDR
            ""
        ]

        for subnet in invalid_subnets:
            with pytest.raises((ValueError, ipaddress.AddressValueError)):
                TailscaleSubnetMiddleware(
                    app=self.mock_app,
                    tailscale_subnet_str=subnet
                )

    @pytest.mark.asyncio
    async def test_middleware_exception_propagation(self):
        """Test that middleware properly propagates exceptions from the app."""
        async def failing_call_next(request):
            raise HTTPException(status_code=500, detail="Internal server error")

        request = Mock(spec=Request)
        request.client.host = "127.0.0.1"

        with pytest.raises(HTTPException) as exc_info:
            await self.middleware.dispatch(request, failing_call_next)

        assert exc_info.value.status_code == 500
        assert exc_info.value.detail == "Internal server error"

    @pytest.mark.asyncio
    async def test_request_modification_preservation(self):
        """Test that middleware preserves request modifications."""
        async def modify_request(request):
            # Simulate downstream middleware modifying the request
            request.state.test_value = "modified"
            return Response(content="OK")

        request = Mock(spec=Request)
        request.client.host = "100.64.0.1"
        request.state = Mock()

        response = await self.middleware.dispatch(request, modify_request)

        assert response.status_code == 200
        assert hasattr(request.state, 'test_value')
        assert request.state.test_value == "modified"


class TestMiddlewareIntegration:
    """Test middleware integration scenarios."""

    def test_multiple_middleware_compatibility(self):
        """Test that Tailscale middleware can work with other middleware."""
        from fastapi import FastAPI
        from fastapi.middleware.cors import CORSMiddleware

        app = FastAPI()

        # Add CORS middleware
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # Add Tailscale middleware
        app.add_middleware(TailscaleSubnetMiddleware, tailscale_subnet_str="100.64.0.0/10")

        # Should not raise any errors during setup
        assert len(app.user_middleware) >= 2

    @pytest.mark.asyncio
    async def test_middleware_logging(self, caplog):
        """Test middleware logging functionality."""
        import logging

        with caplog.at_level(logging.WARNING):
            request = Mock(spec=Request)
            request.client.host = "8.8.8.8"  # External IP

            with pytest.raises(HTTPException):
                await self.middleware.dispatch(request, AsyncMock())

            # Should have logged warning
            assert "Access denied for IP 8.8.8.8" in caplog.text
            assert "outside Tailscale subnet" in caplog.text

    @pytest.mark.asyncio
    async def test_client_ip_edge_cases(self):
        """Test handling of edge cases in client IP detection."""
        call_next = AsyncMock()

        # Test None client IP
        request = Mock(spec=Request)
        request.client.host = None

        with pytest.raises((HTTPException, AttributeError)):
            await self.middleware.dispatch(request, call_next)

        # Test empty string client IP
        request.client.host = ""

        with pytest.raises(HTTPException) as exc_info:
            await self.middleware.dispatch(request, call_next)
        assert exc_info.value.status_code == 400


class TestMiddlewarePerformance:
    """Test middleware performance characteristics."""

    @pytest.mark.asyncio
    async def test_middleware_performance(self):
        """Test middleware performance for valid requests."""
        import time

        call_next = AsyncMock(return_value=Response(content="OK"))
        request = Mock(spec=Request)
        request.client.host = "100.64.0.1"

        # Measure performance of 100 requests
        start_time = time.time()
        for _ in range(100):
            await self.middleware.dispatch(request, call_next)
        end_time = time.time()

        # Should be fast (< 100ms for 100 requests)
        duration = end_time - start_time
        assert duration < 0.1, f"Middleware too slow: {duration}s for 100 requests"

    @pytest.mark.asyncio
    async def test_ip_parsing_cache_behavior(self):
        """Test that IP parsing doesn't create performance bottlenecks."""
        call_next = AsyncMock(return_value=Response(content="OK"))

        # Same IP multiple times should be consistent
        request = Mock(spec=Request)
        request.client.host = "100.64.0.1"

        for _ in range(10):
            response = await self.middleware.dispatch(request, call_next)
            assert response.status_code == 200

        assert call_next.call_count == 10
