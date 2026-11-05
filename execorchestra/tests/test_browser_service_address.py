from Pool.resources.tools.script.browser_read_page import private_service_address


def test_loopback_service_addresses_remain_supported():
    for base in ['http://localhost:8002','http://127.0.0.1:8002','http://[::1]:8002']:
        assert private_service_address(base)


def test_explicit_private_bridge_service_addresses_are_supported():
    for base in ['http://10.253.84.1:8002','http://172.18.0.1:8002','http://192.168.1.1:8002']:
        assert private_service_address(base)


def test_public_metadata_and_credential_bearing_service_addresses_are_rejected():
    for base in ['', 'https://127.0.0.1:8002','http://example.com:8002',
                 'http://8.8.8.8:8002','http://169.254.169.254:8002',
                 'http://0.0.0.0:8002','http://user:password@10.253.84.1:8002']:
        assert not private_service_address(base)


def test_smoke_runner_passes_only_browser_environment_names(monkeypatch):
    from scripts import smoke_tools
    calls=[]
    monkeypatch.setenv('SGAR_BROWSER_BASE_URL','http://10.0.0.1:8002')
    monkeypatch.setenv('SGAR_BROWSER_TOKEN','private-test-browser-token')
    monkeypatch.setattr(smoke_tools,'original_run',lambda command,**kwargs:calls.append(command))
    smoke_tools.run(['docker','run','--rm','image-id','python'])
    assert 'SGAR_BROWSER_BASE_URL' in calls[0] and 'SGAR_BROWSER_TOKEN' in calls[0]
    assert 'private-test-browser-token' not in calls[0] and 'LLM_API_KEY' not in calls[0]
