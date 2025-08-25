# oaDeviceAPI

Unified Device API for OrangeAd device management across macOS and OrangePi/Ubuntu platforms.

## Quick Start

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Run the API:**
   ```bash
   python main.py
   ```

3. **Access the API:**
   - API Documentation: http://localhost:9090/docs
   - Platform Info: http://localhost:9090/platform
   - Health Check: http://localhost:9090/health

## Platform Detection

The API automatically detects your platform:
- **macOS**: Loads camera, tracker, and camguard features
- **OrangePi/Ubuntu**: Loads screenshot and player features
- **Generic Linux**: Basic health monitoring only

## Architecture

```
src/oaDeviceAPI/
├── core/              # Platform detection, config, shared utilities
├── models/            # Unified data schemas 
├── platforms/
│   ├── macos/         # macOS-specific routers and services
│   └── orangepi/      # OrangePi-specific routers and services
└── middleware.py      # Security and CORS middleware
```

## API Endpoints

### Common (All Platforms)
- `GET /` - API information
- `GET /platform` - Platform detection info
- `GET /health` - Raw health metrics
- `GET /health/summary` - Health summary with scoring
- `POST /actions/reboot` - System reboot

### macOS Only
- `GET /cameras` - Camera management
- `GET /tracker/*` - AI tracker integration
- `GET /camguard/*` - Security camera integration

### OrangePi Only  
- `GET /screenshots/*` - Display screenshots
- `POST /actions/restart-player` - Player service management

## Configuration

Set environment variables:
- `OAAPI_PORT=9090` - API port
- `TAILSCALE_SUBNET=100.64.0.0/10` - Security subnet
- `LOG_LEVEL=INFO` - Logging level
- `PLATFORM_OVERRIDE=macos|orangepi` - Force platform

## Development Status

🚀 **Phase 6.1**: Device API unification in progress
- ✅ Repository structure created
- ✅ Platform detection implemented  
- ✅ Core migrations completed
- 🔄 Import path fixes in progress
- ⏳ Testing and validation pending

## Integration

This unified API replaces:
- `oaAnsible/macos-api/` (macOS devices)
- `opi-setup/api/` (OrangePi devices)

Deployed via:
- oaAnsible roles for macOS
- opi-setup scripts for OrangePi
- Both reference this repo as submodule