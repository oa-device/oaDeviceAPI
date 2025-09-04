"""
macOS Security Services Module

This module provides functions to check macOS-specific security features and settings,
including FileVault, Gatekeeper, SIP, Firewall, and Security Updates.
"""

import json
import os
import re

from .utils import run_command


def check_filevault_status() -> dict:
    """
    Check if FileVault is enabled on the system.

    Returns:
        Dict: Status of FileVault encryption
    """
    try:
        # Use fdesetup to check FileVault status
        output = run_command(["fdesetup", "status"])

        # Parse the output
        enabled = "FileVault is On" in output

        # Get more detailed information if enabled
        details = {}
        if enabled:
            try:
                # Get encryption progress if available
                progress_output = run_command(["diskutil", "apfs", "list"])

                # Look for encryption progress information
                progress_match = re.search(
                    r"Encryption Progress:\s+(\d+\.\d+)%", progress_output
                )
                if progress_match:
                    details["progress"] = float(progress_match.group(1))

                # Check for recovery key information
                recovery_output = run_command(
                    ["fdesetup", "hasinstitutionalrecoverykey"]
                )
                details["has_institutional_recovery"] = (
                    "true" in recovery_output.lower()
                )

                personal_recovery_output = run_command(
                    ["fdesetup", "haspersonalrecoverykey"]
                )
                details["has_personal_recovery"] = (
                    "true" in personal_recovery_output.lower()
                )
            except Exception as e:
                details["error"] = str(e)

        return {
            "enabled": enabled,
            "status": "enabled" if enabled else "disabled",
            "details": details,
            "raw_output": output,
        }
    except Exception as e:
        return {"enabled": False, "status": "error", "error": str(e)}


def check_gatekeeper_status() -> dict:
    """
    Check if Gatekeeper is enabled on the system.

    Returns:
        Dict: Status of Gatekeeper
    """
    try:
        # Use spctl to check Gatekeeper status
        output = run_command(["spctl", "--status"])

        # Parse the output
        enabled = "assessments enabled" in output.lower()

        # Get more detailed settings
        details = {}
        try:
            # Check allowed sources
            sources_output = run_command(["spctl", "--list"])

            # Check if App Store apps are allowed
            details["app_store_allowed"] = "AppStore" in sources_output

            # Check if developer ID signed apps are allowed
            details["developer_id_allowed"] = "Developer ID" in sources_output

            # Check if notarized apps are required
            notarization_output = run_command(
                [
                    "defaults",
                    "read",
                    "/Library/Preferences/com.apple.security",
                    "GKAutoUpdateEnabled",
                ]
            )
            details["notarization_required"] = "1" in notarization_output
        except Exception:
            # If we can't get detailed info, just provide the basic status
            pass

        return {
            "enabled": enabled,
            "status": "enabled" if enabled else "disabled",
            "details": details,
            "raw_output": output,
        }
    except Exception as e:
        return {"enabled": False, "status": "error", "error": str(e)}


def check_sip_status() -> dict:
    """
    Check if System Integrity Protection (SIP) is enabled.

    Returns:
        Dict: Status of SIP
    """
    try:
        # Use csrutil to check SIP status
        output = run_command(["csrutil", "status"])

        # Parse the output
        enabled = "enabled" in output.lower() and "disabled" not in output.lower()

        # Check for specific protections if available
        details = {}
        if "Filesystem Protections" in output:
            details["filesystem_protections"] = (
                "enabled"
                in output.split("Filesystem Protections:")[1].split("\n")[0].lower()
            )
        if "Debugging Restrictions" in output:
            details["debugging_restrictions"] = (
                "enabled"
                in output.split("Debugging Restrictions:")[1].split("\n")[0].lower()
            )
        if "DTrace Restrictions" in output:
            details["dtrace_restrictions"] = (
                "enabled"
                in output.split("DTrace Restrictions:")[1].split("\n")[0].lower()
            )
        if "NVRAM Protections" in output:
            details["nvram_protections"] = (
                "enabled"
                in output.split("NVRAM Protections:")[1].split("\n")[0].lower()
            )

        return {
            "enabled": enabled,
            "status": "enabled" if enabled else "disabled",
            "details": details,
            "raw_output": output,
        }
    except Exception as e:
        return {"enabled": False, "status": "error", "error": str(e)}


def check_firewall_status() -> dict:
    """
    Check if the macOS firewall is enabled.

    Returns:
        Dict: Status of the firewall
    """
    try:
        # Use socketfilterfw to check firewall status
        output = run_command(
            ["/usr/libexec/ApplicationFirewall/socketfilterfw", "--getglobalstate"]
        )

        # Parse the output
        enabled = "enabled" in output.lower()

        # Get more detailed settings
        details = {}
        try:
            # Check if stealth mode is enabled
            stealth_output = run_command(
                ["/usr/libexec/ApplicationFirewall/socketfilterfw", "--getstealthmode"]
            )
            details["stealth_mode"] = "enabled" in stealth_output.lower()

            # Check if logging is enabled
            logging_output = run_command(
                ["/usr/libexec/ApplicationFirewall/socketfilterfw", "--getloggingmode"]
            )
            details["logging"] = "enabled" in logging_output.lower()

            # Check if automatic allow signed apps is enabled
            signed_output = run_command(
                ["/usr/libexec/ApplicationFirewall/socketfilterfw", "--getallowsigned"]
            )
            details["allow_signed"] = "ENABLED" in signed_output

            # Get list of allowed apps
            try:
                apps_output = run_command(
                    ["/usr/libexec/ApplicationFirewall/socketfilterfw", "--listapps"]
                )
                allowed_apps = []

                for line in apps_output.split("\n"):
                    if "Allow incoming connections" in line and "YES" in line:
                        app_match = re.search(r'"([^"]+)"', line)
                        if app_match:
                            allowed_apps.append(app_match.group(1))

                details["allowed_apps"] = allowed_apps[
                    :10
                ]  # Limit to 10 apps to avoid excessive data
                details["allowed_apps_count"] = len(allowed_apps)
            except Exception:
                pass
        except Exception as e:
            details["error"] = str(e)

        return {
            "enabled": enabled,
            "status": "enabled" if enabled else "disabled",
            "details": details,
            "raw_output": output,
        }
    except Exception as e:
        return {"enabled": False, "status": "error", "error": str(e)}


def check_security_updates() -> dict:
    """
    Check for pending security updates.

    Returns:
        Dict: Status of security updates
    """
    try:
        # Use softwareupdate to check for updates
        output = run_command(["softwareupdate", "--list"])

        # Parse the output
        has_updates = "No new software available" not in output

        # Extract security updates specifically
        security_updates = []
        recommended_updates = []

        if has_updates:
            for line in output.split("\n"):
                if "Security Update" in line or "security" in line.lower():
                    update_match = re.search(r"\* ([^\(]+)", line)
                    if update_match:
                        security_updates.append(update_match.group(1).strip())
                elif "*" in line:  # Recommended updates are marked with *
                    update_match = re.search(r"\* ([^\(]+)", line)
                    if update_match:
                        recommended_updates.append(update_match.group(1).strip())

        # Check when updates were last installed
        last_update_info = {}
        try:
            # Look at install history
            if os.path.exists("/Library/Receipts/InstallHistory.plist"):
                history_output = run_command(
                    [
                        "plutil",
                        "-convert",
                        "json",
                        "-o",
                        "-",
                        "/Library/Receipts/InstallHistory.plist",
                    ]
                )
                history = json.loads(history_output)

                # Find the most recent security update
                security_installs = [
                    entry
                    for entry in history
                    if "Security Update" in entry.get("displayName", "")
                    or "security" in entry.get("displayName", "").lower()
                ]

                if security_installs:
                    # Sort by date, most recent first
                    security_installs.sort(
                        key=lambda x: x.get("date", ""), reverse=True
                    )
                    most_recent = security_installs[0]

                    last_update_info = {
                        "name": most_recent.get("displayName", "Unknown"),
                        "date": most_recent.get("date", "Unknown"),
                        "version": most_recent.get("displayVersion", "Unknown"),
                    }
        except Exception as e:
            last_update_info["error"] = str(e)

        # Check system update policy
        update_policy = {}
        try:
            auto_check_output = run_command(
                [
                    "defaults",
                    "read",
                    "/Library/Preferences/com.apple.SoftwareUpdate",
                    "AutomaticCheckEnabled",
                ]
            )
            update_policy["automatic_check"] = "1" in auto_check_output

            auto_download_output = run_command(
                [
                    "defaults",
                    "read",
                    "/Library/Preferences/com.apple.SoftwareUpdate",
                    "AutomaticDownload",
                ]
            )
            update_policy["automatic_download"] = "1" in auto_download_output

            critical_updates_output = run_command(
                [
                    "defaults",
                    "read",
                    "/Library/Preferences/com.apple.SoftwareUpdate",
                    "CriticalUpdateInstall",
                ]
            )
            update_policy["install_critical"] = "1" in critical_updates_output
        except Exception:
            # If we can't get update policy, just continue
            pass

        return {
            "has_updates": has_updates,
            "security_updates_available": len(security_updates) > 0,
            "security_updates": security_updates,
            "recommended_updates": recommended_updates,
            "last_security_update": last_update_info,
            "update_policy": update_policy,
            "status": "updates_available" if has_updates else "up_to_date",
            "raw_output": output,
        }
    except Exception as e:
        return {
            "has_updates": False,
            "security_updates_available": False,
            "status": "error",
            "error": str(e),
        }


def check_secure_boot() -> dict:
    """
    Check if Secure Boot is enabled (Apple Silicon and T2 Macs).

    Returns:
        Dict: Status of Secure Boot
    """
    try:
        # Check if system has Secure Boot capability
        output = run_command(["system_profiler", "SPiBridgeDataType"])

        # Check if this is Apple Silicon
        is_apple_silicon = False
        try:
            processor_output = run_command(["sysctl", "-n", "machdep.cpu.brand_string"])
            is_apple_silicon = "Apple" in processor_output
        except Exception:
            pass

        # For Apple Silicon, secure boot is always on
        if is_apple_silicon:
            return {
                "enabled": True,
                "status": "enabled",
                "details": {"platform": "Apple Silicon", "level": "full"},
            }

        # For Intel Macs, check if there's a T2 chip
        has_t2 = "Apple T2" in output

        if not has_t2:
            return {
                "enabled": False,
                "status": "not_supported",
                "details": {"platform": "Intel without T2"},
            }

        # For T2 Macs, check Secure Boot status
        secure_boot_level = "unknown"
        if "Secure Boot: Full Security" in output:
            secure_boot_level = "full"
            enabled = True
        elif "Secure Boot: Medium Security" in output:
            secure_boot_level = "medium"
            enabled = True
        elif "Secure Boot: None" in output or "Secure Boot: No Security" in output:
            secure_boot_level = "none"
            enabled = False
        else:
            # Try to extract the value with regex
            match = re.search(r"Secure Boot:\s*([^\n]+)", output)
            if match:
                value = match.group(1).strip()
                secure_boot_level = value.lower()
                enabled = (
                    "none" not in value.lower() and "no security" not in value.lower()
                )
            else:
                enabled = False

        return {
            "enabled": enabled,
            "status": "enabled" if enabled else "disabled",
            "details": {"platform": "Intel with T2", "level": secure_boot_level},
            "raw_output": output,
        }
    except Exception as e:
        return {"enabled": False, "status": "error", "error": str(e)}


def get_security_overview() -> dict:
    """
    Get a comprehensive overview of macOS security settings.

    Returns:
        Dict: Overview of all security features
    """
    security_status = {
        "filevault": check_filevault_status(),
        "gatekeeper": check_gatekeeper_status(),
        "sip": check_sip_status(),
        "firewall": check_firewall_status(),
        "secure_boot": check_secure_boot(),
        "security_updates": check_security_updates(),
    }

    # Calculate overall security score based on enabled protections
    score = 0
    max_score = 5  # FileVault, Gatekeeper, SIP, Firewall, Secure Boot

    if security_status["filevault"]["enabled"]:
        score += 1
    if security_status["gatekeeper"]["enabled"]:
        score += 1
    if security_status["sip"]["enabled"]:
        score += 1
    if security_status["firewall"]["enabled"]:
        score += 1
    if (
        security_status["secure_boot"]["enabled"]
        or security_status["secure_boot"]["status"] == "not_supported"
    ):
        score += 1

    # Adjust score if security updates are available
    if security_status["security_updates"]["security_updates_available"]:
        score = max(0, score - 1)  # Reduce score by 1 if security updates are needed

    # Calculate percentage and status
    percentage = (score / max_score) * 100

    if percentage >= 80:
        status = "good"
    elif percentage >= 60:
        status = "fair"
    else:
        status = "poor"

    # Add recommendations based on findings
    recommendations = []

    if not security_status["filevault"]["enabled"]:
        recommendations.append(
            "Enable FileVault disk encryption to protect data at rest"
        )

    if not security_status["gatekeeper"]["enabled"]:
        recommendations.append(
            "Enable Gatekeeper to protect against malicious software"
        )

    if not security_status["sip"]["enabled"]:
        recommendations.append(
            "Enable System Integrity Protection (SIP) to protect system files"
        )

    if not security_status["firewall"]["enabled"]:
        recommendations.append(
            "Enable the macOS firewall to protect against network threats"
        )

    if (
        not security_status["secure_boot"]["enabled"]
        and security_status["secure_boot"]["status"] != "not_supported"
    ):
        recommendations.append(
            "Enable Secure Boot for hardware-level security (if supported)"
        )

    if security_status["security_updates"]["security_updates_available"]:
        recommendations.append(
            "Install available security updates to patch vulnerabilities"
        )

    return {
        "status": status,
        "score": score,
        "max_score": max_score,
        "percentage": percentage,
        "features": security_status,
        "recommendations": recommendations,
    }
