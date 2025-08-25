from typing import Dict

from ..core.config import HEALTH_SCORE_THRESHOLDS, HEALTH_SCORE_WEIGHTS


def calculate_health_score(
    metrics: Dict, tracker_status: Dict, display_info: Dict
) -> Dict[str, float]:
    """Calculate health scores for different components and overall system health."""
    try:
        scores = {}

        # CPU Health (0-100)
        cpu_percent = metrics.get("cpu", {}).get("percent", 0)
        scores["cpu"] = max(0, 100 - cpu_percent)

        # Memory Health (0-100)
        memory_percent = metrics.get("memory", {}).get("percent", 0)
        scores["memory"] = max(0, 100 - memory_percent)

        # Disk Health (0-100)
        disk_percent = metrics.get("disk", {}).get("percent", 0)
        scores["disk"] = max(0, 100 - disk_percent)

        # Tracker Health (0 or 100)
        scores["tracker"] = 100 if tracker_status.get("healthy", False) else 0

        # Display Health (0 or 100)
        # For headless systems, we don't penalize for no display
        is_headless = (
            not display_info.get("connected", False)
            and len(display_info.get("displays", [])) == 0
        )
        scores["display"] = (
            100 if display_info.get("connected", False) or is_headless else 0
        )

        # Network Health (0-100)
        network = metrics.get("network", {})
        if network and network.get("interfaces"):
            active_interfaces = sum(
                1 for iface in network["interfaces"].values() if iface.get("up", False)
            )
            total_interfaces = len(network["interfaces"])
            scores["network"] = (
                (active_interfaces / total_interfaces * 100)
                if total_interfaces > 0
                else 0
            )
        else:
            scores["network"] = 0

        # Calculate overall score with weighted average
        overall_score = sum(
            score * HEALTH_SCORE_WEIGHTS[component]
            for component, score in scores.items()
        )
        scores["overall"] = round(overall_score, 2)

        # Add health status levels
        scores["status"] = {
            "critical": overall_score < HEALTH_SCORE_THRESHOLDS["critical"],
            "warning": HEALTH_SCORE_THRESHOLDS["critical"]
            <= overall_score
            < HEALTH_SCORE_THRESHOLDS["warning"],
            "healthy": overall_score >= HEALTH_SCORE_THRESHOLDS["warning"],
        }

        return scores
    except Exception as e:
        return {
            "error": str(e),
            "overall": 0,
            "status": {"critical": True, "warning": False, "healthy": False},
        }


def get_health_summary(metrics: Dict, tracker_status: Dict, display_info: Dict) -> Dict:
    """Get a summary of system health including recommendations."""
    health_scores = calculate_health_score(metrics, tracker_status, display_info)

    recommendations = []
    warnings = []

    # CPU recommendations
    if metrics.get("cpu", {}).get("percent", 0) > 80:
        warnings.append("High CPU usage detected")
        recommendations.append("Check for resource-intensive processes")

    # Memory recommendations
    memory_percent = metrics.get("memory", {}).get("percent", 0)
    if memory_percent > 80:
        warnings.append("High memory usage detected")
        recommendations.append(
            "Consider increasing available memory or check for memory leaks"
        )

    # Disk recommendations
    disk_percent = metrics.get("disk", {}).get("percent", 0)
    if disk_percent > 80:
        warnings.append("Low disk space")
        recommendations.append("Clean up unnecessary files or increase disk space")

    # Tracker recommendations
    if not tracker_status.get("healthy", False):
        warnings.append("Tracker is not running properly")
        if tracker_status.get("service_status") != "active":
            recommendations.append("Check tracker service status")

        # Only check display if system is not headless
        is_headless = (
            not display_info.get("connected", False)
            and len(display_info.get("displays", [])) == 0
        )
        if not tracker_status.get("display_connected", False) and not is_headless:
            recommendations.append("Verify display connection")

    return {
        "scores": health_scores,
        "warnings": warnings,
        "recommendations": recommendations,
        "needs_attention": len(warnings) > 0,
    }
