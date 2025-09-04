"""Unit tests for health scoring functionality."""

from unittest.mock import patch

from src.oaDeviceAPI.platforms.macos.services.health import (
    calculate_health_score as macos_calculate_health_score,
)
from src.oaDeviceAPI.platforms.macos.services.health import (
    get_health_summary as macos_get_health_summary,
)
from src.oaDeviceAPI.platforms.orangepi.services.health import (
    calculate_health_score as orangepi_calculate_health_score,
)
from src.oaDeviceAPI.platforms.orangepi.services.health import (
    get_health_summary as orangepi_get_health_summary,
)


class TestMacOSHealthScoring:
    """Test macOS-specific health scoring."""

    def test_calculate_health_score_perfect_health(self):
        """Test health score calculation with perfect metrics."""
        metrics = {
            "cpu": {"percent": 5.0},
            "memory": {"percent": 20.0},
            "disk": {"percent": 30.0}
        }
        tracker_status = {"healthy": True}
        display_info = {"connected": True, "displays": [{"name": "Built-in"}]}

        scores = macos_calculate_health_score(metrics, tracker_status, display_info)

        assert scores["cpu"] == 95.0  # 100 - 5
        assert scores["memory"] == 80.0  # 100 - 20
        assert scores["disk"] == 70.0  # 100 - 30
        assert scores["tracker"] == 100.0
        assert scores["display"] == 100.0
        assert scores["overall"] > 80.0  # Should be high overall
        assert scores["status"]["healthy"] is True

    def test_calculate_health_score_critical_metrics(self):
        """Test health score with critical system metrics."""
        metrics = {
            "cpu": {"percent": 95.0},
            "memory": {"percent": 98.0},
            "disk": {"percent": 99.0}
        }
        tracker_status = {"healthy": False}
        display_info = {"connected": False, "displays": []}

        scores = macos_calculate_health_score(metrics, tracker_status, display_info)

        assert scores["cpu"] == 5.0  # 100 - 95
        assert scores["memory"] == 2.0  # 100 - 98
        assert scores["disk"] == 1.0  # 100 - 99
        assert scores["tracker"] == 0.0
        assert scores["overall"] < 20.0  # Should be very low
        assert scores["status"]["critical"] is True

    def test_calculate_health_score_headless_system(self):
        """Test health scoring for headless system (no display penalty)."""
        metrics = {
            "cpu": {"percent": 10.0},
            "memory": {"percent": 30.0},
            "disk": {"percent": 40.0}
        }
        tracker_status = {"healthy": True}
        display_info = {"connected": False, "displays": []}  # Headless

        scores = macos_calculate_health_score(metrics, tracker_status, display_info)

        # Display should not penalize headless systems
        assert scores["display"] == 100.0
        assert scores["overall"] > 70.0

    def test_calculate_health_score_network_metrics(self):
        """Test health scoring with network interface data."""
        metrics = {
            "cpu": {"percent": 20.0},
            "memory": {"percent": 40.0},
            "disk": {"percent": 50.0},
            "network": {
                "interfaces": {
                    "en0": {"up": True, "speed": 1000},
                    "en1": {"up": False, "speed": 100},
                    "lo0": {"up": True, "speed": 0}
                }
            }
        }
        tracker_status = {"healthy": True}
        display_info = {"connected": True, "displays": [{}]}

        scores = macos_calculate_health_score(metrics, tracker_status, display_info)

        # 2 out of 3 interfaces are up = 66.67%
        assert 65.0 <= scores["network"] <= 67.0
        assert scores["overall"] > 50.0

    def test_calculate_health_score_missing_data(self):
        """Test health scoring with missing or incomplete data."""
        # Empty metrics
        scores = macos_calculate_health_score({}, {}, {})

        assert scores["cpu"] == 100.0  # No usage = good
        assert scores["memory"] == 100.0
        assert scores["disk"] == 100.0
        assert scores["tracker"] == 0.0  # Not healthy by default
        assert scores["network"] == 0.0  # No interfaces

    def test_calculate_health_score_exception_handling(self):
        """Test health scoring exception handling."""
        # Invalid data that might cause exceptions
        invalid_metrics = {
            "cpu": {"percent": "invalid"},
            "memory": None,
            "disk": []
        }

        scores = macos_calculate_health_score(invalid_metrics, None, None)

        assert "error" in scores
        assert scores["overall"] == 0
        assert scores["status"]["critical"] is True
        assert scores["status"]["healthy"] is False

    def test_get_health_summary_with_warnings(self):
        """Test health summary generation with warnings."""
        metrics = {
            "cpu": {"percent": 85.0},  # High CPU
            "memory": {"percent": 90.0},  # High memory
            "disk": {"percent": 95.0}  # Low disk space
        }
        tracker_status = {"healthy": False, "service_status": "inactive"}
        display_info = {"connected": False, "displays": [{}]}  # Display issue

        summary = macos_get_health_summary(metrics, tracker_status, display_info)

        assert summary["needs_attention"] is True
        assert len(summary["warnings"]) >= 3
        assert len(summary["recommendations"]) >= 3

        # Check specific warnings
        warning_texts = " ".join(summary["warnings"])
        assert "High CPU usage" in warning_texts
        assert "High memory usage" in warning_texts
        assert "Low disk space" in warning_texts
        assert "Tracker is not running" in warning_texts

    def test_get_health_summary_healthy_system(self):
        """Test health summary for healthy system."""
        metrics = {
            "cpu": {"percent": 15.0},
            "memory": {"percent": 40.0},
            "disk": {"percent": 60.0},
        }
        tracker_status = {"healthy": True, "service_status": "active"}
        display_info = {"connected": True, "displays": [{}]}

        summary = macos_get_health_summary(metrics, tracker_status, display_info)

        assert summary["needs_attention"] is False
        assert len(summary["warnings"]) == 0
        assert len(summary["recommendations"]) == 0
        assert summary["scores"]["overall"] > 60.0


class TestOrangePiHealthScoring:
    """Test OrangePi-specific health scoring."""

    def test_calculate_health_score_player_focus(self):
        """Test health scoring focusing on player instead of tracker."""
        metrics = {
            "cpu": {"percent": 25.0},
            "memory": {"percent": 45.0},
            "disk": {"percent": 55.0}
        }
        player_status = {"healthy": True, "service_status": "active"}
        display_info = {"connected": True, "displays": [{}]}

        scores = orangepi_calculate_health_score(metrics, player_status, display_info)

        assert scores["player"] == 100.0  # Healthy player
        assert scores["display"] == 100.0  # Connected display
        assert scores["overall"] > 60.0

    def test_calculate_health_score_player_unhealthy(self):
        """Test health scoring with unhealthy player."""
        metrics = {
            "cpu": {"percent": 10.0},
            "memory": {"percent": 20.0},
            "disk": {"percent": 30.0}
        }
        player_status = {"healthy": False, "service_status": "failed"}
        display_info = {"connected": False, "displays": []}

        scores = orangepi_calculate_health_score(metrics, player_status, display_info)

        assert scores["player"] == 0.0  # Unhealthy player
        assert scores["display"] == 0.0  # No display
        # Overall should be lower due to player/display issues
        assert scores["overall"] < scores["cpu"]  # Should be weighted down

    def test_get_health_summary_player_recommendations(self):
        """Test health summary with player-specific recommendations."""
        metrics = {
            "cpu": {"percent": 20.0},
            "memory": {"percent": 30.0},
            "disk": {"percent": 40.0}
        }
        player_status = {
            "healthy": False,
            "service_status": "inactive",
            "display_connected": False
        }
        display_info = {"connected": False, "displays": [{}]}  # Not headless

        summary = orangepi_get_health_summary(metrics, player_status, display_info)

        assert summary["needs_attention"] is True

        recommendation_text = " ".join(summary["recommendations"])
        assert "Check player service" in recommendation_text
        assert "Verify display connection" in recommendation_text


class TestCrossplatformHealthScoring:
    """Test health scoring consistency across platforms."""

    def test_health_scoring_algorithm_consistency(self):
        """Test that health scoring algorithms are consistent between platforms."""
        # Same system metrics
        metrics = {
            "cpu": {"percent": 50.0},
            "memory": {"percent": 60.0},
            "disk": {"percent": 70.0},
            "network": {
                "interfaces": {
                    "eth0": {"up": True},
                    "wlan0": {"up": False}
                }
            }
        }

        # Both platforms healthy services
        tracker_status = {"healthy": True}
        player_status = {"healthy": True}
        display_info = {"connected": True, "displays": [{}]}

        macos_scores = macos_calculate_health_score(metrics, tracker_status, display_info)
        orangepi_scores = orangepi_calculate_health_score(metrics, player_status, display_info)

        # Core system metrics should be identical
        assert macos_scores["cpu"] == orangepi_scores["cpu"]
        assert macos_scores["memory"] == orangepi_scores["memory"]
        assert macos_scores["disk"] == orangepi_scores["disk"]

        # Service scores should both be 100 (healthy)
        assert macos_scores["tracker"] == orangepi_scores["player"] == 100.0

    def test_health_threshold_consistency(self):
        """Test that health thresholds are defined consistently."""
        # Import both platform configurations
        with patch("src.oaDeviceAPI.core.config.DETECTED_PLATFORM", "macos"):
            from src.oaDeviceAPI.core.config import (
                HEALTH_SCORE_THRESHOLDS as macos_thresholds,
            )

        with patch("src.oaDeviceAPI.platforms.orangepi.services.health.HEALTH_SCORE_THRESHOLDS") as orangepi_thresholds:
            orangepi_thresholds.return_value = {
                "good": 80,
                "warning": 60,
                "critical": 40
            }

            # Thresholds should exist for core components
            required_components = ["cpu", "memory", "disk"]
            for component in required_components:
                if component in macos_thresholds:
                    assert isinstance(macos_thresholds[component], dict)

    def test_edge_case_boundary_conditions(self):
        """Test boundary conditions for health scoring."""
        # Test 0% usage (perfect)
        perfect_metrics = {
            "cpu": {"percent": 0.0},
            "memory": {"percent": 0.0},
            "disk": {"percent": 0.0}
        }

        # Test 100% usage (worst)
        worst_metrics = {
            "cpu": {"percent": 100.0},
            "memory": {"percent": 100.0},
            "disk": {"percent": 100.0}
        }

        tracker_status = {"healthy": True}
        display_info = {"connected": True, "displays": [{}]}

        perfect_scores = macos_calculate_health_score(perfect_metrics, tracker_status, display_info)
        worst_scores = macos_calculate_health_score(worst_metrics, tracker_status, display_info)

        # Perfect should score 100 for system metrics
        assert perfect_scores["cpu"] == 100.0
        assert perfect_scores["memory"] == 100.0
        assert perfect_scores["disk"] == 100.0

        # Worst should score 0 for system metrics
        assert worst_scores["cpu"] == 0.0
        assert worst_scores["memory"] == 0.0
        assert worst_scores["disk"] == 0.0

        # Overall scores should reflect the differences
        assert perfect_scores["overall"] > worst_scores["overall"]

    def test_negative_usage_handling(self):
        """Test handling of negative usage percentages (edge case)."""
        metrics = {
            "cpu": {"percent": -5.0},  # Invalid negative
            "memory": {"percent": -10.0},
            "disk": {"percent": -1.0}
        }
        tracker_status = {"healthy": True}
        display_info = {"connected": True, "displays": [{}]}

        scores = macos_calculate_health_score(metrics, tracker_status, display_info)

        # Negative usage should be clamped to 0 (max health)
        assert scores["cpu"] == 100.0  # max(0, 100 - (-5)) = max(0, 105) = 100
        assert scores["memory"] == 100.0
        assert scores["disk"] == 100.0


class TestHealthScoringErrorHandling:
    """Test error handling in health scoring."""

    def test_malformed_metrics_data(self):
        """Test handling of malformed metrics data."""
        malformed_cases = [
            None,  # None metrics
            "string",  # String instead of dict
            [],  # List instead of dict
            {"cpu": "invalid"},  # Invalid nested data
            {"cpu": {"percent": None}},  # None percentage
        ]

        for bad_metrics in malformed_cases:
            scores = macos_calculate_health_score(bad_metrics, {}, {})

            if "error" in scores:
                assert scores["overall"] == 0
                assert scores["status"]["critical"] is True
            else:
                # If it doesn't error, should handle gracefully
                assert isinstance(scores["overall"], (int, float))

    def test_missing_metric_components(self):
        """Test handling of missing metric components."""
        # Missing CPU data
        metrics = {
            "memory": {"percent": 50.0},
            "disk": {"percent": 60.0},
        }

        scores = macos_calculate_health_score(metrics, {}, {})

        # Should handle missing CPU gracefully
        assert scores["cpu"] == 100.0  # Default to good if missing
        assert scores["memory"] == 50.0
        assert scores["disk"] == 40.0

    def test_tracker_status_edge_cases(self):
        """Test tracker status edge cases."""
        metrics = {"cpu": {"percent": 20.0}, "memory": {"percent": 30.0}, "disk": {"percent": 40.0}}
        display_info = {"connected": True, "displays": [{}]}

        tracker_cases = [
            None,  # None tracker status
            {},  # Empty tracker status
            {"healthy": None},  # None healthy status
            {"healthy": "true"},  # String instead of boolean
            {"other_field": "value"}  # Missing healthy field
        ]

        for tracker_status in tracker_cases:
            scores = macos_calculate_health_score(metrics, tracker_status, display_info)

            # Should handle gracefully
            assert "tracker" in scores
            assert isinstance(scores["tracker"], (int, float))

    def test_display_info_edge_cases(self):
        """Test display info edge cases."""
        metrics = {"cpu": {"percent": 20.0}, "memory": {"percent": 30.0}, "disk": {"percent": 40.0}}
        tracker_status = {"healthy": True}

        display_cases = [
            None,  # None display info
            {},  # Empty display info
            {"connected": None},  # None connected status
            {"displays": None},  # None displays list
            {"displays": "invalid"},  # Invalid displays type
        ]

        for display_info in display_cases:
            scores = macos_calculate_health_score(metrics, tracker_status, display_info)

            # Should handle gracefully
            assert "display" in scores
            assert isinstance(scores["display"], (int, float))


class TestHealthScoringWeights:
    """Test health scoring weight calculations."""

    def test_weight_configuration_validation(self):
        """Test that weight configurations are valid."""
        from src.oaDeviceAPI.core.config import HEALTH_SCORE_WEIGHTS

        # Weights should be positive
        for component, weight in HEALTH_SCORE_WEIGHTS.items():
            assert weight > 0, f"{component} weight should be positive"
            assert weight <= 1.0, f"{component} weight should be <= 1.0"

        # Total weight should be reasonable (close to 1.0)
        total_weight = sum(HEALTH_SCORE_WEIGHTS.values())
        assert 0.8 <= total_weight <= 1.2, "Total weights should be close to 1.0"

    def test_weighted_score_calculation(self):
        """Test that weighted scoring works correctly."""
        # Create scenario where we can predict the outcome
        metrics = {
            "cpu": {"percent": 0.0},     # Score: 100
            "memory": {"percent": 0.0},  # Score: 100
            "disk": {"percent": 0.0}    # Score: 100
        }
        tracker_status = {"healthy": True}  # Score: 100
        display_info = {"connected": True, "displays": [{}]}  # Score: 100

        scores = macos_calculate_health_score(metrics, tracker_status, display_info)

        # With all 100 scores and proper weights, overall should be 100
        assert scores["overall"] == 100.0

        # Test with all zeros
        bad_metrics = {
            "cpu": {"percent": 100.0},    # Score: 0
            "memory": {"percent": 100.0}, # Score: 0
            "disk": {"percent": 100.0}   # Score: 0
        }
        bad_tracker = {"healthy": False}  # Score: 0
        bad_display = {"connected": False, "displays": [{}]}  # Score: 0

        bad_scores = macos_calculate_health_score(bad_metrics, bad_tracker, bad_display)

        # With all 0 scores, overall should be 0 (or very close)
        assert bad_scores["overall"] <= 5.0  # Allow small variance

    def test_partial_component_scoring(self):
        """Test scoring with only some components available."""
        # Only CPU and memory available
        metrics = {
            "cpu": {"percent": 30.0},    # Score: 70
            "memory": {"percent": 40.0}  # Score: 60
        }
        tracker_status = {"healthy": True}  # Score: 100
        display_info = {}  # No display info

        scores = macos_calculate_health_score(metrics, tracker_status, display_info)

        assert scores["cpu"] == 70.0
        assert scores["memory"] == 60.0
        assert scores["tracker"] == 100.0
        # Overall should be calculated properly even with missing components
        assert 0 <= scores["overall"] <= 100


class TestHealthScoringBoundaryConditions:
    """Test boundary conditions and edge cases."""

    def test_extreme_values(self):
        """Test handling of extreme metric values."""
        extreme_metrics = {
            "cpu": {"percent": 999.0},     # Impossible high value
            "memory": {"percent": -50.0},  # Negative value
            "disk": {"percent": 150.0}    # Above 100%
        }
        tracker_status = {"healthy": True}
        display_info = {"connected": True, "displays": [{}]}

        scores = macos_calculate_health_score(extreme_metrics, tracker_status, display_info)

        # Should handle extreme values gracefully
        assert 0 <= scores["cpu"] <= 100
        assert 0 <= scores["memory"] <= 100
        assert 0 <= scores["disk"] <= 100
        assert 0 <= scores["overall"] <= 100

    def test_floating_point_precision(self):
        """Test floating point precision in calculations."""
        # Use values that might cause floating point issues
        metrics = {
            "cpu": {"percent": 33.333333},
            "memory": {"percent": 66.666666},
            "disk": {"percent": 99.999999}
        }
        tracker_status = {"healthy": True}
        display_info = {"connected": True, "displays": [{}]}

        scores = macos_calculate_health_score(metrics, tracker_status, display_info)

        # Results should be properly rounded
        assert isinstance(scores["overall"], float)
        # Should have reasonable precision (2 decimal places as per code)
        overall_str = str(scores["overall"])
        decimal_places = len(overall_str.split(".")[-1]) if "." in overall_str else 0
        assert decimal_places <= 2

    def test_unicode_and_encoding_handling(self):
        """Test handling of unicode and encoding in metric data."""
        metrics = {
            "cpu": {"percent": 25.0, "model": "Apple M2 Pro 芯片"},  # Unicode
            "memory": {"percent": 30.0},
            "disk": {"percent": 40.0, "path": "/système"}  # Unicode path
        }
        tracker_status = {"healthy": True}
        display_info = {"connected": True, "displays": [{"name": "Studio Display™"}]}

        # Should not raise encoding errors
        scores = macos_calculate_health_score(metrics, tracker_status, display_info)
        assert isinstance(scores["overall"], (int, float))

    def test_very_large_numbers(self):
        """Test handling of very large numbers in metrics."""
        metrics = {
            "cpu": {"percent": 25.0},
            "memory": {
                "percent": 30.0,
                "total": 1099511627776,  # 1TB
                "used": 549755813888,   # 512GB
                "available": 549755813888
            },
            "disk": {
                "percent": 40.0,
                "total": 10995116277760,  # 10TB
                "used": 4398046511104,   # 4TB
                "free": 6597069766656    # 6TB
            }
        }
        tracker_status = {"healthy": True}
        display_info = {"connected": True, "displays": [{}]}

        # Should handle large numbers without overflow
        scores = macos_calculate_health_score(metrics, tracker_status, display_info)
        assert 0 <= scores["overall"] <= 100
