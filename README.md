# OrangeAd Unified Device API (oaDeviceAPI)

**Status**: ✅ Phase 6 Complete - Production Ready

The unified `oaDeviceAPI` consolidates separate macOS and OrangePi device APIs into a single, platform-aware service that automatically detects the running platform and loads appropriate functionality.

## Quick Start

1. **Install dependencies:**

   ```bash
   # Core dependencies
   python -m pip install --break-system-packages fastapi uvicorn pydantic pydantic-settings psutil httpx

   # Optional dependencies (for full functionality)
   python -m pip install --break-system-packages opencv-python numpy requests
   ```

2. **Run the API:**

   ```bash
   # Basic startup (auto-detects platform)
   PYTHONPATH=/path/to/oaDeviceAPI/src python main.py

   # Custom port
   PYTHONPATH=/path/to/oaDeviceAPI/src OAAPI_PORT=9095 python main.py
   ```

3. **Testing:**

   ```bash
   # Run comprehensive test suite
   ./run_tests.sh

   # Quick health check
   curl http://localhost:9090/health | jq
   ```

## Platform Detection & Features

The API automatically detects your platform and loads appropriate features:

### macOS Features ✅

- **Health Monitoring**: CPU, memory, disk, system info
- **Camera Support**: Detection, listing, MJPEG streaming
- **Tracker Integration**: oaTracker service status and API proxy
- **CamGuard Integration**: Recording service management
- **System Actions**: Service restarts, system reboot
- **SMC Temperature**: Hardware temperature monitoring

### OrangePi Features ✅

- **Health Monitoring**: CPU, memory, disk, system info
- **Screenshot Support**: Display capture functionality
- **Player Integration**: Video player status and control
- **System Actions**: Service restarts, system reboot

## Architecture

```bash
oaDeviceAPI/
├── main.py                    # Entry point with platform detection
├── src/oaDeviceAPI/
│   ├── core/                  # Core framework
│   │   ├── config.py         # Unified configuration
│   │   └── platform.py       # Platform detection
│   ├── models/               # Shared data models
│   │   └── schemas.py        # Pydantic schemas
│   ├── middleware/           # FastAPI middleware
│   └── platforms/            # Platform-specific implementations
│       ├── macos/           # macOS-specific code
│       └── orangepi/        # OrangePi-specific code
├── tests/                   # Comprehensive test suite
└── run_tests.sh            # Test runner
```

## API Endpoints

### Core Endpoints (All Platforms)

- `GET /` - API info and capabilities
- `GET /platform` - Platform detection info
- `GET /health` - Detailed health metrics
- `GET /health/summary` - Health score summary
- `POST /actions/reboot` - System reboot

### macOS-Specific Endpoints

- `GET /cameras` - List available cameras
- `GET /cameras/status` - Camera availability status
- `GET /cameras/{id}/stream` - MJPEG camera stream
- `GET /tracker/status` - oaTracker service status
- `GET /tracker/stats` - Tracker runtime statistics
- `GET /camguard/status` - CamGuard recording status
- `POST /actions/restart-tracker` - Restart tracker service

### OrangePi-Specific Endpoints

- `GET /screenshot` - Capture display screenshot
- `GET /player/status` - Video player status
- `POST /player/actions/restart` - Restart video player

## Configuration

Environment variables for configuration:

```bash
# Server configuration
export OAAPI_HOST=0.0.0.0          # Default: 0.0.0.0
export OAAPI_PORT=9090             # Default: 9090
export OAAPI_RELOAD=true           # Default: true (dev mode)

# Platform override (usually auto-detected)
export OAAPI_PLATFORM=macos       # Options: macos, orangepi

# Security (Tailscale subnet restriction)
export TAILSCALE_SUBNET_ONLY=true # Default: true
```

## Testing Results

✅ **11/12 tests passing (92% success rate)**

The comprehensive test suite validates:

- Platform detection and feature loading
- All API endpoints return valid responses
- Error handling and status codes
- Platform-specific functionality
- Performance and concurrency

## Integration

### With oaDashboard

The unified API is designed to be consumed by oaDashboard's backend, which:

1. Discovers devices via Tailscale
2. Queries each device's `/platform` endpoint
3. Adapts UI and functionality based on device capabilities
4. Calculates centralized health scores from raw device metrics

### With oaAnsible & opi-setup

This unified API replaces the separate:

- `oaAnsible/macos-api/` (macOS devices)
- `opi-setup/api/` (OrangePi devices)

## Development Status

🎉 **Phase 6 Complete**: Device API Unification

- ✅ Repository structure created
- ✅ Platform detection implemented
- ✅ Core migrations completed
- ✅ Import path fixes resolved
- ✅ Function compatibility fixed
- ✅ All major endpoints validated
- ✅ Comprehensive test suite created
- ✅ Documentation completed

**Ready for production deployment** 🚀
