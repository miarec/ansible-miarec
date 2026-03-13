import json
import os
import testinfra.utils.ansible_runner

testinfra_hosts = testinfra.utils.ansible_runner.AnsibleRunner(
    os.environ['MOLECULE_INVENTORY_FILE']).get_hosts('all')

miarec_version = os.environ.get('MIAREC_VERSION')


def test_directories(host):

    dirs = [
        "/opt/miarec/releases/{}".format(miarec_version),
        "/opt/miarec/shared",
        "/var/log/miarec",
        "/var/log/miarec/cdr",
        "/var/log/miarec/error",
        "/var/log/miarec/trace",
        "/var/miarec/recordings"
    ]
    for dir in dirs:
        d = host.file(dir)
        assert d.is_directory
        assert d.exists

def test_files(host):
    files = [
        "/opt/miarec/releases/{}/miarec".format(miarec_version),
        "/opt/miarec/releases/{}/miarec.ini".format(miarec_version)
    ]

    for file in files:
        f = host.file(file)
        assert f.exists
        assert f.is_file

def test_service(host):
    services = [
        "miarec"
    ]

    for service in services:
        s = host.service(service)
        assert s.is_enabled
        assert s.is_running

def test_socket(host):
    sockets = [
        "tcp://0.0.0.0:9080",
        "tcp://0.0.0.0:5080",
        "tcp://0.0.0.0:6554",
        "tcp://0.0.0.0:6088"
    ]
    for socket in sockets:
        s = host.socket(socket)
        assert s.is_listening


def test_health_endpoint(host):
    """Verify /health endpoint returns healthy status for dependencies."""
    # MiaRec REST API listens on port 6088
    result = host.run("curl -fsS http://localhost:6088/health")
    assert result.rc == 0, f"Health endpoint not reachable: {result.stderr}"

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(
            f"Health endpoint response is not valid JSON: {exc}\n"
            f"Response: {result.stdout}"
        )

    assert payload.get("status") == "ok", f"Unexpected overall status: {payload}"
    assert payload.get("database") == "ok", f"Unexpected database status: {payload}"
    assert payload.get("redis") == "ok", f"Unexpected Redis status: {payload}"
