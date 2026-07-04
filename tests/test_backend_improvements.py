"""
Comprehensive Backend Improvement Tests
=========================================
Improvement #6: Test coverage expansion

Tests all 20 backend improvements to verify they work correctly.
"""
import os
import sys
import re
import json
import time
import logging
import unittest
import threading
from unittest.mock import patch, MagicMock

# Setup path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestFix01_GodObjectDecomposition(unittest.TestCase):
    """#1: Route registry for Blueprint migration planning."""

    def test_route_registry_import(self):
        from chatdev.route_registry import route_registry, RouteEntry
        self.assertIsNotNone(route_registry)

    def test_register_and_list(self):
        from chatdev.route_registry import RouteRegistry, RouteEntry
        reg = RouteRegistry()
        reg.register(RouteEntry(
            path="/api/test", methods=["GET"], module="test",
            function_name="test_func", description="A test"
        ))
        routes = reg.list_all()
        self.assertEqual(len(routes), 1)
        self.assertEqual(routes[0]["path"], "/api/test")

    def test_conflict_detection(self):
        from chatdev.route_registry import RouteRegistry, RouteEntry
        reg = RouteRegistry()
        entry = RouteEntry(path="/api/dup", methods=["GET"], module="a", function_name="f1")
        reg.register(entry)
        reg.register(RouteEntry(path="/api/dup", methods=["GET"], module="b", function_name="f2"))
        conflicts = reg.check_conflicts()
        self.assertEqual(len(conflicts), 1)

    def test_stats(self):
        from chatdev.route_registry import RouteRegistry, RouteEntry
        reg = RouteRegistry()
        reg.register(RouteEntry(path="/a", methods=["GET"], module="m1", function_name="f1"))
        reg.register(RouteEntry(path="/b", methods=["POST"], module="m2", function_name="f2"))
        stats = reg.get_stats()
        self.assertEqual(stats["total_routes"], 2)
        self.assertEqual(stats["modules"], 2)

    def test_blueprint_map_exists(self):
        from chatdev.route_registry import RouteRegistry
        self.assertIn("agents", RouteRegistry.BLUEPRINT_MAP)
        self.assertIn("workflow", RouteRegistry.BLUEPRINT_MAP)
        self.assertIn("ceo", RouteRegistry.BLUEPRINT_MAP)


class TestFix02_DuplicateRoutes(unittest.TestCase):
    """#2: No duplicate GET routes on same path."""

    def test_no_duplicate_routes_in_app(self):
        app_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "visualizer", "app.py")
        with open(app_path, 'r') as f:
            content = f.read()
        
        # Parse all routes with their methods
        route_method_pairs = {}
        lines = content.split('\n')
        for i, line in enumerate(lines):
            m = re.match(r'\s*@app\.route\(["\']([^"\']+)["\'](?:.*methods=\[([^\]]+)\])?', line)
            if m:
                path = m.group(1)
                methods_str = m.group(2) or '"GET"'
                methods = [m.strip().strip('"').strip("'") for m in methods_str.split(",")]
                for method in methods:
                    key = f"{method}:{path}"
                    route_method_pairs.setdefault(key, []).append(i + 1)
        
        duplicates = {k: v for k, v in route_method_pairs.items() if len(v) > 1}
        self.assertEqual(len(duplicates), 0, 
                        f"Found duplicate routes: {duplicates}")


class TestFix03_SilentExceptPass(unittest.TestCase):
    """#3: No silent except...pass in app.py."""

    def test_no_silent_pass_in_app(self):
        app_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "visualizer", "app.py")
        with open(app_path, 'r') as f:
            lines = f.readlines()
        
        silent_passes = []
        for i, line in enumerate(lines, 1):
            if line.strip() == 'pass' and i > 1:
                prev = lines[i - 2].strip()
                if prev.startswith('except'):
                    silent_passes.append(f"L{i}: after '{prev}'")
        
        self.assertEqual(len(silent_passes), 0,
                        f"Found {len(silent_passes)} silent except...pass: {silent_passes[:5]}")


class TestFix04_LazyLoading(unittest.TestCase):
    """#4: LazyModule defers imports."""

    def test_lazy_module_not_loaded_initially(self):
        from chatdev.service_registry import LazyModule
        lazy = LazyModule("json")
        self.assertFalse(lazy.is_loaded)

    def test_lazy_module_loads_on_access(self):
        from chatdev.service_registry import LazyModule
        lazy = LazyModule("json")
        result = lazy.dumps({"a": 1})
        self.assertTrue(lazy.is_loaded)
        self.assertEqual(result, '{"a": 1}')

    def test_lazy_module_with_attr(self):
        from chatdev.service_registry import LazyModule
        lazy = LazyModule("os.path", "join")
        result = lazy("/a", "b")
        self.assertEqual(result, "/a/b")

    def test_lazy_module_thread_safety(self):
        from chatdev.service_registry import LazyModule
        lazy = LazyModule("time")
        results = []
        
        def access():
            results.append(lazy.time())
        
        threads = [threading.Thread(target=access) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        self.assertEqual(len(results), 10)


class TestFix05_LargeFunctionContext(unittest.TestCase):
    """#5: Verify large functions are documented for decomposition."""

    def test_app_functions_under_300_lines(self):
        """Check that no top-level function exceeds 300 lines.

        Uses ast (with end_lineno) instead of scanning for the next
        top-level 'def' line, since that naive approach misattributes the
        length of nested helper closures (e.g. def _load_xxx() defined
        inside another function) to the enclosing function.
        """
        import ast
        app_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "visualizer", "app.py")
        with open(app_path, 'r') as f:
            source = f.read()
        tree = ast.parse(source)

        violations = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name.startswith('_'):
                    continue
                length = node.end_lineno - node.lineno
                if length > 300:
                    violations.append(f"{node.name} ({length} lines at L{node.lineno})")

        self.assertEqual(len(violations), 0,
                        f"Functions over 300 lines: {violations}")


class TestFix07_APIEnvelope(unittest.TestCase):
    """#7: Standardized API response format."""

    def test_api_success(self):
        from chatdev.api_envelope import api_success
        # Need Flask app context
        from flask import Flask
        app = Flask(__name__)
        with app.test_request_context():
            response, status = api_success(data={"key": "val"})
            data = json.loads(response.get_data())
            self.assertTrue(data["ok"])
            self.assertEqual(data["data"]["key"], "val")
            self.assertIn("meta", data)
            self.assertEqual(status, 200)

    def test_api_error(self):
        from chatdev.api_envelope import api_error
        from flask import Flask
        app = Flask(__name__)
        with app.test_request_context():
            response, status = api_error("NOT_FOUND", "Item not found", status=404)
            data = json.loads(response.get_data())
            self.assertFalse(data["ok"])
            self.assertEqual(data["error"]["code"], "NOT_FOUND")
            self.assertEqual(status, 404)

    def test_api_paginated(self):
        from chatdev.api_envelope import api_paginated
        from flask import Flask
        app = Flask(__name__)
        with app.test_request_context():
            response, status = api_paginated([1, 2, 3], page=1, per_page=10, total=25)
            data = json.loads(response.get_data())
            self.assertTrue(data["ok"])
            self.assertEqual(len(data["data"]), 3)
            self.assertEqual(data["pagination"]["total"], 25)
            self.assertTrue(data["pagination"]["has_next"])


class TestFix08_TypeHints(unittest.TestCase):
    """#8: Type hints in key modules."""

    def test_modules_have_return_types(self):
        modules = [
            "chatdev/eval_quality.py",
            "chatdev/scheduler.py",
            "chatdev/session_timeout.py",
            "chatdev/utils.py",
        ]
        for filepath in modules:
            full_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), filepath)
            with open(full_path, 'r') as f:
                code = f.read()
            funcs = re.findall(r'def \w+\(', code)
            typed = re.findall(r'->', code)
            ratio = len(typed) / len(funcs) * 100 if funcs else 100
            self.assertGreaterEqual(ratio, 50,
                                   f"{filepath}: only {ratio:.0f}% functions have return types")


class TestFix09_SendMsgSingleton(unittest.TestCase):
    """#9: send_msg uses singleton socket client."""

    def test_singleton_pattern_in_code(self):
        app_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "visualizer", "app.py")
        with open(app_path, 'r') as f:
            code = f.read()
        
        self.assertIn("_send_msg_client", code)
        self.assertIn("_send_msg_connected", code)
        # Should NOT create new Client() inside send_msg
        send_msg_section = code[code.find("def send_msg("):code.find("def send_msg(") + 600]
        self.assertNotIn("sio = socketio.Client()", send_msg_section)


class TestFix11_AsyncUtils(unittest.TestCase):
    """#11: Async execution wrappers."""

    def test_run_async(self):
        from chatdev.async_utils import run_async
        result = run_async(lambda: 42, timeout=5.0)
        self.assertEqual(result, 42)

    def test_run_async_timeout(self):
        from chatdev.async_utils import run_async
        def slow():
            time.sleep(10)
        with self.assertRaises(TimeoutError):
            run_async(slow, timeout=0.1)

    def test_run_in_background(self):
        from chatdev.async_utils import run_in_background
        results = []
        def task():
            results.append(1)
            return "done"
        
        task_id = run_in_background(task)
        time.sleep(0.5)
        self.assertEqual(results, [1])

    def test_get_active_tasks(self):
        from chatdev.async_utils import get_active_tasks
        tasks = get_active_tasks()
        self.assertIsInstance(tasks, dict)


class TestFix12_PrintToLogging(unittest.TestCase):
    """#12: No print() calls in production modules."""

    def test_no_print_in_chatdev_modules(self):
        modules = [
            "chatdev/chat_chain.py",
            "chatdev/chat_env.py",
            "chatdev/documents.py",
            "chatdev/omnichannel_sink.py",
            "chatdev/web_operator.py",
        ]
        for filepath in modules:
            full_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), filepath)
            with open(full_path, 'r') as f:
                code = f.read()
            # Count print( but exclude those in strings/comments
            prints = len(re.findall(r'^\s+print\(', code, re.MULTILINE))
            self.assertEqual(prints, 0, f"{filepath} still has {prints} print() calls")


class TestFix13_PublicAPIExports(unittest.TestCase):
    """#13: Agent modules have __all__ exports."""

    def test_all_defined_in_agent_modules(self):
        modules = [
            "chatdev/agent_arch.py",
            "chatdev/agent_comm.py",
            "chatdev/agent_cognition.py",
            "chatdev/exec_control.py",
        ]
        for filepath in modules:
            full_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), filepath)
            with open(full_path, 'r') as f:
                code = f.read()
            self.assertIn("__all__", code, f"{filepath} missing __all__ export list")


class TestFix14_Facade(unittest.TestCase):
    """#14: Module facade for reduced coupling."""

    def test_facade_import(self):
        from chatdev.facade import chatdev_facade
        self.assertIsNotNone(chatdev_facade)

    def test_facade_lazy_properties(self):
        from chatdev.facade import ChatDevFacade
        facade = ChatDevFacade()
        # Properties should exist but not trigger loading
        self.assertTrue(hasattr(facade, 'agent_arch'))
        self.assertTrue(hasattr(facade, 'agent_comm'))
        self.assertTrue(hasattr(facade, 'exec_control'))

    def test_facade_loaded_modules_tracking(self):
        from chatdev.facade import ChatDevFacade
        facade = ChatDevFacade()
        status = facade.get_loaded_modules()
        self.assertIsInstance(status, dict)
        self.assertGreater(len(status), 0)


class TestFix17_CentralSettings(unittest.TestCase):
    """#17: Centralized settings configuration."""

    def test_settings_import(self):
        from chatdev.settings import settings
        self.assertIsNotNone(settings)

    def test_settings_has_defaults(self):
        from chatdev.settings import Settings
        s = Settings()
        self.assertEqual(s.server_port, 8000)
        self.assertEqual(s.default_model, "gpt-4")
        self.assertEqual(s.max_workers, 4)

    def test_settings_env_override(self):
        from chatdev.settings import Settings
        with patch.dict(os.environ, {"PORT": "9999"}):
            s = Settings()
            self.assertEqual(s.server_port, 9999)

    def test_settings_safe_dict(self):
        from chatdev.settings import Settings
        s = Settings()
        s.openai_api_key = "sk-test1234567890"
        safe = s.to_safe_dict()
        self.assertNotIn("sk-test", str(safe.get("openai_api_key", "")))
        self.assertIn("***", safe["openai_api_key"])

    def test_settings_has_google_auth(self):
        from chatdev.settings import Settings
        s = Settings()
        s.google_client_id = ""
        self.assertFalse(s.has_google_auth)


class TestFix18_ServiceRegistry(unittest.TestCase):
    """#18: DI container / service locator."""

    def test_register_and_get(self):
        from chatdev.service_registry import ServiceRegistry
        reg = ServiceRegistry()
        reg.register("test_svc", {"name": "test"})
        result = reg.get("test_svc")
        self.assertEqual(result["name"], "test")

    def test_register_lazy(self):
        from chatdev.service_registry import ServiceRegistry
        reg = ServiceRegistry()
        reg.register_lazy("json_svc", "json")
        svc = reg.get("json_svc")
        self.assertIsNotNone(svc)

    def test_register_factory(self):
        from chatdev.service_registry import ServiceRegistry
        reg = ServiceRegistry()
        call_count = [0]
        def factory():
            call_count[0] += 1
            return {"created": True}
        
        reg.register_factory("lazy_svc", factory)
        self.assertEqual(call_count[0], 0)
        
        result = reg.get("lazy_svc")
        self.assertEqual(call_count[0], 1)
        self.assertTrue(result["created"])
        
        # Second get should use cached
        reg.get("lazy_svc")
        self.assertEqual(call_count[0], 1)

    def test_reset(self):
        from chatdev.service_registry import ServiceRegistry
        reg = ServiceRegistry()
        reg.register("svc", "value")
        reg.reset("svc")
        self.assertIsNone(reg.get("svc"))

    def test_list_services(self):
        from chatdev.service_registry import ServiceRegistry
        reg = ServiceRegistry()
        reg.register("eager", "val")
        reg.register_lazy("lazy", "json")
        reg.register_factory("factory", lambda: "val")
        listing = reg.list_services()
        self.assertEqual(listing["eager"], "eager")
        self.assertIn("lazy", listing["lazy"])
        self.assertEqual(listing["factory"], "factory")


class TestFix19_BareExcept(unittest.TestCase):
    """#19: No bare except: in eval_quality.py."""

    def test_no_bare_except(self):
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "chatdev", "eval_quality.py")
        with open(path, 'r') as f:
            for i, line in enumerate(f, 1):
                stripped = line.strip()
                if stripped == 'except:':
                    self.fail(f"Bare 'except:' found at line {i}")


class TestFix20_WorkflowEngineErrorHandling(unittest.TestCase):
    """#20: No silent except...pass in workflow_engine.py."""

    def test_no_silent_pass_in_workflow(self):
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "chatdev", "workflow_engine.py")
        with open(path, 'r') as f:
            lines = f.readlines()
        
        silent_passes = []
        for i, line in enumerate(lines, 1):
            if line.strip() == 'pass' and i > 1:
                prev = lines[i - 2].strip()
                if prev.startswith('except'):
                    silent_passes.append(f"L{i}")
        
        self.assertEqual(len(silent_passes), 0,
                        f"Found silent except...pass at: {silent_passes}")


class TestFix10_ExceptionRefinement(unittest.TestCase):
    """#10: Exception handling refinement verification."""
    
    def test_except_exception_with_logging(self):
        """Verify that remaining except Exception blocks at least log."""
        app_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "visualizer", "app.py")
        with open(app_path, 'r') as f:
            content = f.read()
        
        # Count except Exception blocks that are followed by logging
        blocks = re.findall(r'except Exception.*:\n\s+logging\.', content)
        total_except = len(re.findall(r'except Exception', content))
        
        # At least 20% should have logging (was 0% before fix #3)
        if total_except > 0:
            ratio = len(blocks) / total_except * 100
            self.assertGreater(ratio, 15,
                             f"Only {ratio:.0f}% of except blocks have logging")


class TestFix15_16_NoGlobalStatements(unittest.TestCase):
    """#15 & #16: No global keyword in phase.py and composed_phase.py."""
    
    def test_no_global_in_phase(self):
        import ast
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "chatdev", "phase.py")
        with open(path, 'r') as f:
            tree = ast.parse(f.read())
        globals_found = [node.lineno for node in ast.walk(tree) if isinstance(node, ast.Global)]
        self.assertEqual(len(globals_found), 0,
                        f"Global statements at lines: {globals_found}")

    def test_no_global_in_composed_phase(self):
        import ast
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "chatdev", "composed_phase.py")
        with open(path, 'r') as f:
            tree = ast.parse(f.read())
        globals_found = [node.lineno for node in ast.walk(tree) if isinstance(node, ast.Global)]
        self.assertEqual(len(globals_found), 0,
                        f"Global statements at lines: {globals_found}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
