import json
import sys
from types import SimpleNamespace

import pytest

from entity.configs import Node
from entity.configs.node.python_runner import PythonRunnerConfig
from runtime.node.executor.python_executor import PythonNodeExecutor


@pytest.mark.parametrize("override", [None, "configured value"])
def test_python_child_receives_configured_and_runtime_environment(tmp_path, monkeypatch, override):
    monkeypatch.setenv("CHATDEV_TEST_INHERITED", "parent value")
    config_env = {} if override is None else {"CHATDEV_TEST_INHERITED": override}
    config_env["CHATDEV_TEST_EXTRA"] = "额外 value"
    config_env["MAC_NODE_ID"] = "incorrect override"
    config = PythonRunnerConfig(path="node.config", interpreter=sys.executable, env=config_env)
    node = Node(path="node", id="python-node", type="python", config=config)
    script = tmp_path / "environment.py"
    script.write_text(
        'import json, os\n'
        'keys = ["CHATDEV_TEST_INHERITED", "CHATDEV_TEST_EXTRA", '
        '"MAC_NODE_ID", "MAC_CODE_SCRIPT", "MAC_CODE_WORKSPACE"]\n'
        'print(json.dumps({key: os.environ.get(key) for key in keys}))\n',
        encoding="utf-8",
    )
    executor = PythonNodeExecutor(SimpleNamespace(global_state={}))
    result = executor._run_process(config, script, tmp_path, node)
    assert result.success, result.stderr
    child = json.loads(result.stdout)
    assert child == {
        "CHATDEV_TEST_INHERITED": override or "parent value",
        "CHATDEV_TEST_EXTRA": "额外 value",
        "MAC_NODE_ID": node.id,
        "MAC_CODE_SCRIPT": str(script),
        "MAC_CODE_WORKSPACE": str(tmp_path),
    }
    assert config.env == config_env
