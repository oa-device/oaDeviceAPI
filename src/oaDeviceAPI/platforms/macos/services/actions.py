import asyncio
import logging

from ....core.config import LAUNCHCTL_CMD

logger = logging.getLogger(__name__)


class ActionsService:
    """Service for handling macOS device actions like reboot and tracker restart."""

    async def reboot_device(self) -> str:
        """
        Reboot the macOS device using the 'shutdown -r now' command.

        Returns:
            str: Output from the reboot command
        """
        try:
            # Use the shutdown command to reboot the device
            process = await asyncio.create_subprocess_exec(
                "sudo",
                "shutdown",
                "-r",
                "now",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                error_msg = stderr.decode().strip() if stderr else "Unknown error"
                logger.error(f"Reboot command failed: {error_msg}")
                raise RuntimeError(f"Reboot command failed: {error_msg}")

            return "Reboot command executed successfully"
        except Exception as e:
            logger.exception("Failed to execute reboot command")
            raise RuntimeError(f"Failed to execute reboot command: {str(e)}")

    async def restart_tracker(self) -> str:
        """
        Restart the tracker service on macOS using launchctl.

        Returns:
            str: Output from the restart command
        """
        try:
            # Get the tracker service plist name
            tracker_plist = "com.orangead.tracker"

            # Unload the service
            unload_process = await asyncio.create_subprocess_exec(
                LAUNCHCTL_CMD,
                "unload",
                f"~/Library/LaunchAgents/{tracker_plist}.plist",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            unload_stdout, unload_stderr = await unload_process.communicate()

            if unload_process.returncode != 0:
                error_msg = (
                    unload_stderr.decode().strip() if unload_stderr else "Unknown error"
                )
                logger.warning(
                    f"Tracker unload warning (might be normal if not running): {error_msg}"
                )

            # Small delay to ensure the service is fully unloaded
            await asyncio.sleep(1)

            # Load the service
            load_process = await asyncio.create_subprocess_exec(
                LAUNCHCTL_CMD,
                "load",
                f"~/Library/LaunchAgents/{tracker_plist}.plist",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            load_stdout, load_stderr = await load_process.communicate()

            if load_process.returncode != 0:
                error_msg = (
                    load_stderr.decode().strip() if load_stderr else "Unknown error"
                )
                logger.error(f"Tracker load failed: {error_msg}")
                raise RuntimeError(f"Tracker load failed: {error_msg}")

            return "Tracker service restarted successfully"
        except Exception as e:
            logger.exception("Failed to restart tracker service")
            raise RuntimeError(f"Failed to restart tracker service: {str(e)}")
