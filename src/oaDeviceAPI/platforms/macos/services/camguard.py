import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from oaDeviceAPI.core.utils import run_command_detailed

logger = logging.getLogger(__name__)

# CamGuard configuration
CAMGUARD_SERVICE_NAME = "com.orangead.camguard"
CAMGUARD_CLEANUP_SERVICE_NAME = "com.orangead.camguard.cleanup"
CAMGUARD_BASE_DIR = os.path.expanduser("~/orangead/camguard")
RECORDINGS_DIR = os.path.join(CAMGUARD_BASE_DIR, "recordings")
LOGS_DIR = os.path.join(CAMGUARD_BASE_DIR, "logs")
SCRIPTS_DIR = os.path.join(CAMGUARD_BASE_DIR, "scripts")


def run_command(command: List[str], timeout: int = 10) -> Dict[str, Any]:
    """Run a shell command and return the result"""
    result = run_command_detailed(command, timeout)
    return {
        "success": result["success"],
        "returncode": result["returncode"],
        "stdout": result["stdout"],
        "stderr": result["stderr"],
    }


def get_camguard_service_status() -> Dict[str, Any]:
    """Get the status of CamGuard LaunchAgent services"""
    try:
        # Check main CamGuard service
        main_service = run_command(["launchctl", "list", CAMGUARD_SERVICE_NAME])
        cleanup_service = run_command(["launchctl", "list", CAMGUARD_CLEANUP_SERVICE_NAME])
        
        # Parse launchctl output for main service
        main_running = main_service.get("success", False)
        main_pid = None
        if main_running and main_service.get("stdout"):
            lines = main_service["stdout"].split("\n")
            for line in lines:
                if line.strip():
                    parts = line.split("\t")
                    if len(parts) >= 1 and parts[0].isdigit():
                        main_pid = int(parts[0])
                        break
        
        # Check if ffmpeg process is running
        ffmpeg_check = run_command(["pgrep", "-f", "ffmpeg.*avfoundation"])
        ffmpeg_running = ffmpeg_check.get("success", False)
        ffmpeg_pid = None
        if ffmpeg_running and ffmpeg_check.get("stdout"):
            try:
                ffmpeg_pid = int(ffmpeg_check["stdout"].split("\n")[0])
            except (ValueError, IndexError):
                pass
        
        return {
            "service_loaded": main_running,
            "service_pid": main_pid,
            "running": main_running and main_pid is not None,
            "ffmpeg_running": ffmpeg_running,
            "ffmpeg_pid": ffmpeg_pid,
            "cleanup_service_loaded": cleanup_service.get("success", False),
            "timestamp": datetime.now().isoformat(),
        }
        
    except Exception as e:
        logger.error(f"Error checking CamGuard service status: {str(e)}")
        return {
            "service_loaded": False,
            "running": False,
            "ffmpeg_running": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }


def get_recording_status() -> Dict[str, Any]:
    """Get the current recording status and statistics"""
    try:
        recordings_path = Path(RECORDINGS_DIR)
        logs_path = Path(LOGS_DIR)
        
        # Check if directories exist
        if not recordings_path.exists():
            return {
                "recording_active": False,
                "error": "Recordings directory does not exist",
                "timestamp": datetime.now().isoformat(),
            }
        
        # Get recording files
        recording_files = list(recordings_path.glob("rec-*.mp4"))
        recording_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        
        # Get the most recent recording
        latest_recording = None
        recording_active = False
        if recording_files:
            latest_file = recording_files[0]
            latest_recording = {
                "filename": latest_file.name,
                "size_bytes": latest_file.stat().st_size,
                "created": datetime.fromtimestamp(latest_file.stat().st_ctime).isoformat(),
                "modified": datetime.fromtimestamp(latest_file.stat().st_mtime).isoformat(),
            }
            
            # Check if file was modified recently (within last 2 minutes = active recording)
            time_since_modified = time.time() - latest_file.stat().st_mtime
            recording_active = time_since_modified < 120  # 2 minutes
        
        # Calculate storage usage
        total_size = sum(f.stat().st_size for f in recording_files)
        
        # Check available disk space
        disk_usage = os.statvfs(str(recordings_path))
        available_bytes = disk_usage.f_bavail * disk_usage.f_frsize
        disk_full = available_bytes < (1024 * 1024 * 1024)  # Less than 1GB available
        
        # Read recent log entries
        log_file = logs_path / "camguard.log"
        recent_logs = []
        if log_file.exists():
            try:
                with open(log_file, 'r') as f:
                    lines = f.readlines()
                    recent_logs = [line.strip() for line in lines[-10:]]  # Last 10 lines
            except Exception as e:
                logger.warning(f"Could not read log file: {str(e)}")
        
        return {
            "recording_active": recording_active,
            "latest_recording": latest_recording,
            "total_recordings": len(recording_files),
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "available_space_bytes": available_bytes,
            "available_space_gb": round(available_bytes / (1024 * 1024 * 1024), 2),
            "disk_full": disk_full,
            "recent_logs": recent_logs,
            "timestamp": datetime.now().isoformat(),
        }
        
    except Exception as e:
        logger.error(f"Error getting recording status: {str(e)}")
        return {
            "recording_active": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }


def get_recordings_list(limit: int = 50) -> List[Dict[str, Any]]:
    """Get a list of recent recordings with metadata"""
    try:
        recordings_path = Path(RECORDINGS_DIR)
        
        if not recordings_path.exists():
            return []
        
        recording_files = list(recordings_path.glob("rec-*.mp4"))
        recording_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        
        recordings = []
        for file_path in recording_files[:limit]:
            try:
                stat = file_path.stat()
                recordings.append({
                    "filename": file_path.name,
                    "size_bytes": stat.st_size,
                    "size_mb": round(stat.st_size / (1024 * 1024), 2),
                    "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "duration_minutes": 5,  # Approximate based on chunk duration
                })
            except Exception as e:
                logger.warning(f"Error processing file {file_path}: {str(e)}")
                continue
        
        return recordings
        
    except Exception as e:
        logger.error(f"Error getting recordings list: {str(e)}")
        return []


def get_storage_info() -> Dict[str, Any]:
    """Get storage usage and configuration information"""
    try:
        recordings_path = Path(RECORDINGS_DIR)
        
        if not recordings_path.exists():
            return {
                "error": "Recordings directory does not exist",
                "timestamp": datetime.now().isoformat(),
            }
        
        # Calculate directory size
        recording_files = list(recordings_path.glob("rec-*.mp4"))
        total_size = sum(f.stat().st_size for f in recording_files)
        
        # Get disk usage
        disk_usage = os.statvfs(str(recordings_path))
        total_disk = disk_usage.f_blocks * disk_usage.f_frsize
        available_disk = disk_usage.f_bavail * disk_usage.f_frsize
        used_disk = total_disk - available_disk
        
        return {
            "recordings_directory": str(recordings_path),
            "total_recordings": len(recording_files),
            "recordings_size_bytes": total_size,
            "recordings_size_gb": round(total_size / (1024 * 1024 * 1024), 3),
            "disk_total_gb": round(total_disk / (1024 * 1024 * 1024), 2),
            "disk_used_gb": round(used_disk / (1024 * 1024 * 1024), 2),
            "disk_available_gb": round(available_disk / (1024 * 1024 * 1024), 2),
            "disk_usage_percent": round((used_disk / total_disk) * 100, 1),
            "timestamp": datetime.now().isoformat(),
        }
        
    except Exception as e:
        logger.error(f"Error getting storage info: {str(e)}")
        return {
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }


def get_camguard_config() -> Dict[str, Any]:
    """Get CamGuard recording configuration (simulated from expected values)"""
    # This would normally read from a config file, but for now we'll return expected defaults
    return {
        "recording": {
            "resolution": "1920x1080",
            "framerate": 30,
            "chunk_duration": 300
        }
    }




def restart_camguard_service() -> Dict[str, Any]:
    """Restart the CamGuard service"""
    try:
        logger.info("Restarting CamGuard service")
        
        # Stop the service
        stop_result = run_command([
            "launchctl", "unload", 
            os.path.expanduser(f"~/Library/LaunchAgents/{CAMGUARD_SERVICE_NAME}.plist")
        ])
        
        # Wait a moment
        time.sleep(2)
        
        # Start the service
        start_result = run_command([
            "launchctl", "load", "-w",
            os.path.expanduser(f"~/Library/LaunchAgents/{CAMGUARD_SERVICE_NAME}.plist")
        ])
        
        return {
            "success": start_result.get("success", False),
            "stop_result": stop_result,
            "start_result": start_result,
            "timestamp": datetime.now().isoformat(),
        }
        
    except Exception as e:
        logger.error(f"Error restarting CamGuard service: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }


def trigger_cleanup() -> Dict[str, Any]:
    """Manually trigger the CamGuard cleanup script"""
    try:
        logger.info("Triggering CamGuard cleanup")
        
        cleanup_script = os.path.join(SCRIPTS_DIR, "camguard_cleanup.sh")
        
        if not os.path.exists(cleanup_script):
            return {
                "success": False,
                "error": f"Cleanup script not found at {cleanup_script}",
                "timestamp": datetime.now().isoformat(),
            }
        
        # Run cleanup script
        result = run_command(["bash", cleanup_script], timeout=60)
        
        return {
            "success": result.get("success", False),
            "output": result.get("stdout", ""),
            "error": result.get("stderr", ""),
            "timestamp": datetime.now().isoformat(),
        }
        
    except Exception as e:
        logger.error(f"Error triggering cleanup: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }


def get_stream_url() -> Dict[str, Any]:
    """Get RTSP stream URL and streaming status"""
    try:
        import socket
        import requests
        
        # Get hostname for RTSP URL
        hostname = socket.gethostname()
        
        # Default streaming configuration (matches camguard defaults)
        rtsp_port = 8554
        stream_path = "live"
        rtsp_url = f"rtsp://{hostname}:{rtsp_port}/{stream_path}"
        
        # Check if MediaMTX service is running
        mediamtx_running = False
        mediamtx_result = run_command(["launchctl", "list", "com.orangead.mediamtx"])
        if mediamtx_result.get("success", False):
            mediamtx_running = True
        
        # Check if MediaMTX API is responding
        server_status = "offline"
        stream_active = False
        
        if mediamtx_running:
            try:
                # Check MediaMTX API endpoint
                response = requests.get(f"http://127.0.0.1:9997", timeout=2)
                if response.status_code == 200:
                    server_status = "online"
                    
                    # Check if the live stream path is active
                    try:
                        paths_response = requests.get(f"http://127.0.0.1:9997/v3/paths/list", timeout=2)
                        if paths_response.status_code == 200:
                            paths_data = paths_response.json()
                            # Check if our stream path exists and has publishers
                            for path_info in paths_data.get("items", []):
                                if path_info.get("name") == stream_path:
                                    publishers = path_info.get("sourceReady", False)
                                    if publishers:
                                        stream_active = True
                                    break
                    except Exception as e:
                        logger.debug(f"Could not check stream status: {e}")
                        
            except requests.RequestException as e:
                logger.debug(f"MediaMTX API not responding: {e}")
                server_status = "error"
        
        return {
            "rtsp_url": rtsp_url,
            "enabled": True,  # Streaming is enabled by default in new config
            "active": stream_active,
            "server_status": server_status,
            "mediamtx_running": mediamtx_running,
            "port": rtsp_port,
            "stream_path": stream_path,
            "timestamp": datetime.now().isoformat(),
        }
        
    except Exception as e:
        logger.error(f"Error getting stream URL: {str(e)}")
        return {
            "rtsp_url": None,
            "enabled": False,
            "active": False,
            "server_status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }


