"""
Backend Improvement V3 Tests
==============================
Tests for the 30-item V3 backend roadmap improvements.
Covers: #4, #10, #14, #15, #16, #18, #22, #23, #26, #29
"""
import os
import sys
import re
import json
import time
import logging
import unittest
import threading

# Setup path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _visualizer_source_files(root_dir):
    """app.py plus every blueprint module.

    Route handlers that used to live directly in visualizer/app.py have
    largely been extracted into visualizer/blueprints/*.py; several tests
    below need to grep across both to reflect where the code actually is.
    """
    paths = [os.path.join(root_dir, "visualizer", "app.py")]
    blueprints_dir = os.path.join(root_dir, "visualizer", "blueprints")
    if os.path.isdir(blueprints_dir):
        for name in sorted(os.listdir(blueprints_dir)):
            if name.endswith(".py"):
                paths.append(os.path.join(blueprints_dir, name))
    return paths


class TestV3_04_PathConstants(unittest.TestCase):
    """#4: ROOT_DIR and path constants are defined."""

    def test_root_dir_defined(self):
        """ROOT_DIR is defined at module level."""
        app_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "visualizer", "app.py")
        with open(app_path, 'r') as f:
            content = f.read()
        self.assertIn("ROOT_DIR = ", content)
        self.assertIn("COMPANY_CONFIG_DIR = ", content)
        self.assertIn("TEAMS_DIR = ", content)

    def test_no_inline_root_dir_calculation(self):
        """Ensure most os.path.dirname chains have been replaced."""
        app_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "visualizer", "app.py")
        with open(app_path, 'r') as f:
            content = f.read()
        # Count remaining inline calculations (should be minimal)
        inline_count = content.count("os.path.dirname(os.path.dirname(os.path.abspath(__file__)))")
        # Allow up to 5 (some are in comments, string constants, etc.)
        self.assertLessEqual(inline_count, 5,
                            f"Found {inline_count} inline ROOT_DIR calculations")


class TestV3_10_DBUnification(unittest.TestCase):
    """#10: Both database.py and backend_utils.py use same default DB path."""

    def test_same_default_db_name(self):
        """Both files default to ceo_commands.db when CHATDEV_DB_PATH is not set."""
        db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                               "visualizer", "backend", "database.py")
        with open(db_path, 'r') as f:
            db_content = f.read()

        utils_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                  "visualizer", "backend_utils.py")
        with open(utils_path, 'r') as f:
            utils_content = f.read()

        self.assertIn("ceo_commands.db", db_content)
        self.assertIn("ceo_commands.db", utils_content)

    def test_env_var_configurable(self):
        """Both files read CHATDEV_DB_PATH environment variable."""
        db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                               "visualizer", "backend", "database.py")
        with open(db_path, 'r') as f:
            content = f.read()
        self.assertIn("CHATDEV_DB_PATH", content)


class TestV3_14_SecretKey(unittest.TestCase):
    """#14: Secret key is never hardcoded."""

    def test_no_hardcoded_secret(self):
        """Ensure the old hardcoded secret is replaced."""
        app_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "visualizer", "app.py")
        with open(app_path, 'r') as f:
            content = f.read()
        self.assertNotIn("chatdev_enterprise_secret_key!", content)

    def test_urandom_fallback(self):
        """Secret key fallback uses os.urandom."""
        app_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "visualizer", "app.py")
        with open(app_path, 'r') as f:
            content = f.read()
        self.assertIn("os.urandom", content)


class TestV3_15_PathTraversal(unittest.TestCase):
    """#15: Path traversal defense."""

    def test_validate_team_name_import(self):
        """validate_team_name function exists."""
        app_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "visualizer", "app.py")
        with open(app_path, 'r') as f:
            content = f.read()
        self.assertIn("def validate_team_name(", content)
        self.assertIn("def sanitize_path_component(", content)

    def test_traversal_blocked_in_code(self):
        """Routes that use team_name call validate_team_name.

        Many of the routes that originally lived in app.py have since been
        extracted into visualizer/blueprints/*.py, so the calls to
        validate_team_name() now live there too.
        """
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        count = 0
        for path in _visualizer_source_files(root_dir):
            with open(path, 'r') as f:
                count += f.read().count("validate_team_name(")
        self.assertGreaterEqual(count, 3, f"Only {count} calls to validate_team_name")


class TestV3_16_SafeErrorResponse(unittest.TestCase):
    """#16: Error responses don't leak internal info."""

    def test_safe_error_response_exists(self):
        """safe_error_response function exists."""
        app_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "visualizer", "app.py")
        with open(app_path, 'r') as f:
            content = f.read()
        self.assertIn("def safe_error_response(", content)

    def test_safe_error_used_in_routes(self):
        """Routes use safe_error_response instead of raw str(e).

        Route handlers now live in visualizer/blueprints/*.py rather than
        app.py, so the usages of safe_error_response() are checked there too.
        """
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        count = 0
        for path in _visualizer_source_files(root_dir):
            with open(path, 'r') as f:
                count += f.read().count("safe_error_response(")
        self.assertGreaterEqual(count, 3, f"Only {count} uses of safe_error_response")


class TestV3_18_StructuredRequestLogging(unittest.TestCase):
    """#18: Structured JSON request logging."""

    def test_access_logger_exists(self):
        """Access logger is configured."""
        app_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "visualizer", "app.py")
        with open(app_path, 'r') as f:
            content = f.read()
        self.assertIn('_access_logger = logging.getLogger("access")', content)
        self.assertIn("_structured_request_log", content)

    def test_server_timing_header(self):
        """Server-Timing header is added to responses."""
        app_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "visualizer", "app.py")
        with open(app_path, 'r') as f:
            content = f.read()
        self.assertIn("Server-Timing", content)


class TestV3_22_UUIDFilenames(unittest.TestCase):
    """#22: Workflow gallery uses UUID-based filenames."""

    def test_uuid_in_save_workflow(self):
        """save_workflow_snapshot uses UUID for filename.

        save_workflow_snapshot now lives in
        visualizer/blueprints/misc_routes_bp.py rather than app.py.
        """
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        idx = -1
        content = ""
        for path in _visualizer_source_files(root_dir):
            with open(path, 'r') as f:
                content = f.read()
            idx = content.find("def save_workflow_snapshot(")
            if idx > 0:
                break
        self.assertGreater(idx, 0, "save_workflow_snapshot() not found in app.py or blueprints")
        func_block = content[idx:idx + 800]
        self.assertIn("uuid", func_block.lower())
        self.assertIn("file_id", func_block)


class TestV3_23_TelemetryRetention(unittest.TestCase):
    """#23: Telemetry data retention policy."""

    def test_cleanup_method_exists(self):
        """TelemetryEngine has cleanup_old_events method."""
        state_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                  "visualizer", "backend", "state_engine.py")
        with open(state_path, 'r') as f:
            content = f.read()
        self.assertIn("def cleanup_old_events(", content)
        self.assertIn("RETENTION_DAYS", content)

    def test_cleanup_in_flush_loop(self):
        """Cleanup runs periodically in flush loop."""
        state_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                  "visualizer", "backend", "state_engine.py")
        with open(state_path, 'r') as f:
            content = f.read()
        self.assertIn("cleanup_old_events()", content)
        self.assertIn("_cleanup_counter", content)


class TestV3_26_StructuredLogging(unittest.TestCase):
    """#26: Consistent structured JSON logging."""

    def test_json_formatter_exists(self):
        """StructuredJsonFormatter class exists in app.py."""
        app_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "visualizer", "app.py")
        with open(app_path, 'r') as f:
            content = f.read()
        self.assertIn("class StructuredJsonFormatter", content)

    def test_chatdev_loggers_configured(self):
        """chatdev namespace loggers use structured formatter."""
        app_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "visualizer", "app.py")
        with open(app_path, 'r') as f:
            content = f.read()
        self.assertIn('"chatdev"', content)
        self.assertIn('"chatdev.database"', content)
        self.assertIn('"access"', content)


class TestV3_29_ResponseEnvelope(unittest.TestCase):
    """#29: Standardized response envelope helpers."""

    def test_api_success_exists(self):
        """api_success helper function exists."""
        app_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "visualizer", "app.py")
        with open(app_path, 'r') as f:
            content = f.read()
        self.assertIn("def api_success(", content)

    def test_api_error_exists(self):
        """api_error helper function exists."""
        app_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "visualizer", "app.py")
        with open(app_path, 'r') as f:
            content = f.read()
        self.assertIn("def api_error(", content)


class TestV3_GracefulShutdown(unittest.TestCase):
    """#27: Graceful shutdown is implemented."""

    def test_signal_handlers_registered(self):
        """SIGTERM and SIGINT handlers are registered."""
        app_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "visualizer", "app.py")
        with open(app_path, 'r') as f:
            content = f.read()
        self.assertIn("signal.signal(signal.SIGTERM", content)
        self.assertIn("signal.signal(signal.SIGINT", content)
        self.assertIn("_graceful_shutdown", content)


class TestV3_HealthEndpoints(unittest.TestCase):
    """#25: Unified health check endpoints."""

    def test_liveness_endpoint(self):
        """GET /health exists.

        The health routes now live in visualizer/blueprints/ (registered by
        several blueprints), not directly in app.py.
        """
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        found = any(
            '"/health"' in open(path).read()
            for path in _visualizer_source_files(root_dir)
        )
        self.assertTrue(found, '"/health" route not found in app.py or blueprints')

    def test_readiness_endpoint(self):
        """GET /health/ready exists.

        Same as above: the readiness route was extracted into a blueprint.
        """
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        found = any(
            '"/health/ready"' in open(path).read()
            for path in _visualizer_source_files(root_dir)
        )
        self.assertTrue(found, '"/health/ready" route not found in app.py or blueprints')


if __name__ == "__main__":
    unittest.main(verbosity=2)
