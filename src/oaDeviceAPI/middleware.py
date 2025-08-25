"""Middleware for oaDeviceAPI."""

import ipaddress
import logging
from typing import Callable

from fastapi import Request, Response, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class TailscaleSubnetMiddleware(BaseHTTPMiddleware):
    """Middleware to restrict access to Tailscale subnet."""
    
    def __init__(self, app, tailscale_subnet_str: str):
        super().__init__(app)
        self.tailscale_subnet = ipaddress.ip_network(tailscale_subnet_str, strict=False)
        logger.info(f"Tailscale subnet restriction enabled for {tailscale_subnet_str}")
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Check if the request is from within the Tailscale subnet."""
        client_ip = request.client.host
        
        # Skip check for localhost and development
        if client_ip in ["127.0.0.1", "::1", "localhost"]:
            return await call_next(request)
        
        try:
            client_ip_obj = ipaddress.ip_address(client_ip)
            if client_ip_obj not in self.tailscale_subnet:
                logger.warning(f"Access denied for IP {client_ip} - outside Tailscale subnet")
                raise HTTPException(
                    status_code=403,
                    detail="Access denied: Must be connected via Tailscale"
                )
        except ValueError:
            logger.warning(f"Invalid IP address format: {client_ip}")
            raise HTTPException(
                status_code=400,
                detail="Invalid client IP address"
            )
        
        return await call_next(request)