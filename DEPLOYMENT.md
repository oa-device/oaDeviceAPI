# oaDeviceAPI Deployment Guide

## Integration Strategy

The unified oaDeviceAPI replaces platform-specific APIs in both oaAnsible and opi-setup repositories.

## Integration Points

### oaAnsible Integration (macOS devices)

**Current**: `oaAnsible/macos-api/` - deployed as standalone service
**Target**: `oaDeviceAPI` submodule - unified API deployment

#### Changes Required:

1. **Update ansible role**: `roles/macos/api/`
   - Reference oaDeviceAPI submodule instead of local macos-api
   - Update service deployment paths
   - Modify LaunchAgent configuration

2. **Service Configuration**:
   ```yaml
   # Before
   service_path: "{{ ansible_user_dir }}/orangead/macos-api"
   
   # After  
   service_path: "{{ ansible_user_dir }}/orangead/oaDeviceAPI"
   ```

3. **Binary Integration**:
   - `bin/macos/smctemp` already migrated to oaDeviceAPI
   - Update deployment scripts to use unified structure

### opi-setup Integration (OrangePi devices)

**Current**: `opi-setup/api/` - embedded API service
**Target**: `oaDeviceAPI` submodule - unified API deployment

#### Changes Required:

1. **Submodule Setup**:
   ```bash
   cd opi-setup
   git submodule add https://github.com/oa-device/oaDeviceAPI.git api-unified
   ```

2. **Service Configuration**:
   - Update systemd service: `health-check-api.service`
   - Modify startup scripts to use unified entry point
   - Update API paths in shell scripts

3. **Directory Structure**:
   ```
   opi-setup/
   ├── api-unified/           # oaDeviceAPI submodule
   ├── api/                  # Legacy - to be deprecated
   └── systemd/
       └── health-check-api.service  # Updated service
   ```

## Deployment Workflow

### Phase 1: Parallel Deployment
- Deploy unified API alongside existing APIs
- Validate functionality on test devices
- Gradual migration of endpoint consumers

### Phase 2: Primary Deployment  
- Switch primary service to unified API
- Keep legacy APIs as fallback
- Monitor for compatibility issues

### Phase 3: Legacy Removal
- Remove deprecated API directories
- Clean up old service configurations
- Complete migration to unified structure

## Configuration Management

### Environment Variables
```bash
# Platform detection override (optional)
PLATFORM_OVERRIDE=macos|orangepi

# API configuration
OAAPI_PORT=9090
OAAPI_HOST=0.0.0.0

# Security
TAILSCALE_SUBNET=100.64.0.0/10

# Logging
LOG_LEVEL=INFO
```

### Platform-Specific Configs

#### macOS (via oaAnsible)
```yaml
oaapi_config:
  port: 9090
  macos_bin_dir: "{{ ansible_user_dir }}/orangead/oaDeviceAPI/bin/macos"
  service_timeout: 30
```

#### OrangePi (via opi-setup)
```bash
# Environment file: /etc/orangead/oaapi.env
OAAPI_PORT=9090
SCREENSHOT_DIR=/tmp/screenshots
ORANGEPI_PLAYER_SERVICE=slideshow-player.service
```

## Service Management

### macOS (LaunchAgent)
```xml
<!-- com.orangead.deviceapi.plist -->
<key>ProgramArguments</key>
<array>
    <string>{{ python_path }}</string>
    <string>{{ ansible_user_dir }}/orangead/oaDeviceAPI/main.py</string>
</array>
```

### OrangePi (systemd)
```ini
# health-check-api.service
[Service]
Type=simple
ExecStart=/usr/bin/python3 /opt/orangead/oaDeviceAPI/main.py
WorkingDirectory=/opt/orangead/oaDeviceAPI
Environment=OAAPI_PORT=9090
```

## Testing Strategy

### Pre-deployment Testing
1. **Structure Validation**: `python test_structure.py`
2. **Unit Tests**: `python -m pytest tests/unit/`
3. **Integration Tests**: `python -m pytest tests/integration/`
4. **E2E Tests**: `python -m pytest tests/e2e/`

### Deployment Validation
1. **Health Endpoint**: `curl http://device:9090/health`
2. **Platform Detection**: `curl http://device:9090/platform`
3. **Feature Availability**: Validate platform-specific endpoints
4. **Service Status**: Check systemd/launchctl status

## Rollback Strategy

### Emergency Rollback
1. **Stop unified service**: `systemctl stop health-check-api`
2. **Start legacy service**: `systemctl start legacy-api`  
3. **Revert DNS/proxy**: Update load balancer configuration
4. **Notify monitoring**: Alert monitoring systems of rollback

### Gradual Rollback
1. **Traffic splitting**: Route percentage of traffic back to legacy
2. **Monitor metrics**: Watch for performance/error differences
3. **Progressive rollback**: Increase legacy traffic percentage
4. **Complete rollback**: Full traffic back to legacy if needed

## Monitoring & Observability

### Health Checks
- **Endpoint**: `GET /health/summary`
- **Expected Response Time**: <500ms
- **Success Criteria**: HTTP 200 with valid JSON

### Platform Metrics
- **CPU Usage**: Via `/health` endpoint
- **Memory Usage**: Via `/health` endpoint  
- **Disk Usage**: Via `/health` endpoint
- **Service Status**: Platform-specific service monitoring

### Error Monitoring
- **HTTP Error Rates**: 4xx/5xx response monitoring
- **Platform Detection**: Validate correct platform identification
- **Feature Availability**: Monitor platform-specific feature status

## Security Considerations

### Network Security
- **Tailscale Only**: All endpoints restricted to Tailscale subnet
- **CORS Configuration**: Restricted to dashboard origins
- **No External Access**: API not exposed to public internet

### Service Security  
- **User Context**: Run as non-root user (orangead/ansible_user)
- **File Permissions**: Restrict access to configuration files
- **Binary Security**: macOS binaries signed and verified

### Data Security
- **No Sensitive Data**: Health metrics only, no credentials
- **Encrypted Transit**: HTTPS via Tailscale tunnel
- **Audit Logging**: Service start/stop events logged