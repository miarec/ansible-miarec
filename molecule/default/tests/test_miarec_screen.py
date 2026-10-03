import json
import os
import testinfra.utils.ansible_runner

testinfra_hosts = testinfra.utils.ansible_runner.AnsibleRunner(
    os.environ['MOLECULE_INVENTORY_FILE']).get_hosts('all')

miarec_screen_version = os.environ.get('MIAREC_SCREEN_VERSION')


def test_directories(host):
    dirs = [
        "/opt/miarec_screen/releases/{}".format(miarec_screen_version),
        "/opt/miarec_screen/shared",
        "/var/log/miarec_screen",
        "/var/log/miarec_screen/error",
        "/var/log/miarec_screen/trace"
    ]
    for dir in dirs:
        d = host.file(dir)
        assert d.exists, f"Directory {dir} does not exist"
        assert d.is_directory


def test_files(host):
    files = [
        "/opt/miarec_screen/releases/{}/miarec_screen".format(miarec_screen_version),
        "/opt/miarec_screen/releases/{}/miarec_screen.ini".format(miarec_screen_version)
    ]
    for file in files:
        f = host.file(file)
        assert f.exists, f"File {file} does not exist"
        assert f.is_file


def test_service(host):
    s = host.service("miarec_screen")
    assert s.is_enabled
    assert s.is_running


def test_socket(host):
    # 6089 is the REST API; 6091 and 6092 accept client connections over TCP and TLS
    for socket in ["tcp://0.0.0.0:6089", "tcp://0.0.0.0:6091", "tcp://0.0.0.0:6092"]:
        assert host.socket(socket).is_listening, f"Socket {socket} is not listening"


def test_health_endpoint(host):
    """Verify /health endpoint returns healthy status for dependencies."""
    # MiaRec screen controller REST API listens on port 6089
    result = host.run("curl -fsS http://localhost:6089/health")
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
