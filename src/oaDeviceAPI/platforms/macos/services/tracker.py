import os
from datetime import UTC, datetime

import psutil

from ....core.config import LAUNCHCTL_CMD, PS_CMD, TRACKER_ROOT
from ..services.display import get_display_info
from ..services.system import get_service_info
from ..services.utils import run_command


def check_tracker_status() -> dict[str, str]:
    """Check if the oaTracker is running."""
    try:
        # Check if tracker service is active (assuming it will be named com.orangead.tracker)
        service_active = "active" in run_command(
            [LAUNCHCTL_CMD, "list", "com.orangead.tracker"]
        )

        # Check if tracker process is running
        tracker_running = False
        ps_output = run_command([PS_CMD, "aux"])
        tracker_running = "oaTracker" in ps_output

        # Get display status
        display_info = get_display_info()

        # Get process details if running
        process_info = None
        tracker_start_time = None
        if tracker_running:
            try:
                for proc in psutil.process_iter(
                    ["pid", "cpu_percent", "memory_percent", "create_time"]
                ):
                    if "oaTracker" in proc.name():
                        create_time = datetime.fromtimestamp(
                            proc.create_time(), UTC
                        )
                        tracker_start_time = create_time.isoformat()
                        process_info = {
                            "pid": proc.pid,
                            "cpu_usage": proc.cpu_percent(),
                            "memory_usage": proc.memory_percent(),
                            "start_time": tracker_start_time,
                        }
                        break
            except Exception:
                pass

        return {
            "service_status": "active" if service_active else "inactive",
            "tracker_status": "running" if tracker_running else "stopped",
            "display_connected": display_info.get("connected", False),
            "healthy": service_active and tracker_running,
            "process": process_info,
            "tracker_start_time": tracker_start_time,
        }
    except Exception as e:
        return {
            "service_status": "unknown",
            "tracker_status": "unknown",
            "display_connected": False,
            "healthy": False,
            "error": str(e),
        }


def get_deployment_info() -> dict:
    """Get deployment information for the tracker."""
    try:
        # Get service statuses
        services = {
            "tracker": get_service_info("com.orangead.tracker"),
            "api": get_service_info("com.orangead.macosapi"),
        }

        # Get display information
        display = get_display_info()

        # Get last reboot time from psutil
        try:
            boot_timestamp = psutil.boot_time()
            boot_datetime = datetime.fromtimestamp(boot_timestamp, UTC)
            last_reboot = boot_datetime.isoformat()
        except Exception:
            last_reboot = datetime.now(UTC).isoformat()

        # Get tracker version
        version = "unknown"
        version_file = TRACKER_ROOT / "version.txt"
        if version_file.exists():
            version = version_file.read_text().strip()

        # Check last sync if applicable
        last_sync = None
        last_sync_epoch = None
        sync_log_dir = TRACKER_ROOT / "logs"
        if sync_log_dir.exists():
            try:
                sync_logs = list(sync_log_dir.glob("*.log"))
                if sync_logs:
                    latest_log = max(sync_logs, key=os.path.getctime)
                    sync_time = datetime.fromtimestamp(os.path.getctime(latest_log))
                    sync_time_utc = sync_time.astimezone(UTC)
                    last_sync = sync_time_utc.isoformat()
                    last_sync_epoch = int(sync_time_utc.timestamp())
            except Exception:
                pass

        # Determine overall status
        service_status = all(svc["status"] == "active" for svc in services.values())

        deployment_info = {
            "status": "active" if service_status else "inactive",
            "version": version,
            "install_path": str(TRACKER_ROOT),
            "last_update": datetime.now(UTC).isoformat(),
            "last_reboot": last_reboot,
            "last_sync": last_sync,
            "last_sync_epoch": last_sync_epoch,
            "services": services,
            "display": display,
        }

        # Remove None values
        return {k: v for k, v in deployment_info.items() if v is not None}
    except Exception as e:
        return {
            "status": "unknown",
            "error": str(e),
            "last_update": datetime.now(UTC).isoformat(),
        }
