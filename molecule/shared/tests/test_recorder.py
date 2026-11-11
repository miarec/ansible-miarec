"""Recorder tier: the call recorder."""
import pytest
import miarec_apps
from conftest import hosts_in, process_owners, listening_on_all_interfaces, needs_tls, run_as, \
    MIAREC_TLS_DIR, MIAREC_VERSION, RECORDER_REST_PORT

testinfra_hosts = hosts_in('recorder')

GROUP = "recorder"
SERVICE = "miarec"
PORT = RECORDER_REST_PORT


def test_service(host):
    s = host.service(SERVICE)
    assert s.is_enabled
    assert s.is_running


def test_process_user(host):
    assert process_owners(host, "miarec") == {("miarec", "miarec")}


def test_recorder_can_write_recordings(host):
    """The service user can create files in the recordings directory.

    miarec_instance_name defaults to the inventory hostname.
    """
    directory = f"/var/recordings/{host.ansible.get_variables()['inventory_hostname']}"
    probe = f"{directory}/.molecule-write-test"
    result = run_as(host, "miarec", f"touch {probe} && rm {probe}")
    assert result.rc == 0, f"The miarec user cannot write to {directory}: {result.stderr}"


def test_listening(host):
    # SIP, RTSP live monitoring, REST API, and the internal HTTP port
    for port in [5080, 6554, PORT, 9080]:
        assert listening_on_all_interfaces(host, port), f"The recorder does not listen on port {port}"


def test_health_endpoint(host):
    miarec_apps.assert_health_from_web(host, GROUP, PORT)


def test_registered_in_database(host):
    miarec_apps.assert_registered(host, "recorders", "TRUE", "miarec")


def test_db_connections_use_tls(host):
    miarec_apps.assert_db_connections(host, GROUP)


@pytest.mark.parametrize("client_group", miarec_apps.REST_CLIENT_GROUPS)
def test_rest_api_allows_miarecweb(host, client_group):
    miarec_apps.assert_rest_api_allows(host, GROUP, PORT, client_group, MIAREC_VERSION)


@pytest.mark.parametrize("client_name", miarec_apps.other_hosts_params(GROUP))
def test_rest_api_rejects_other_hosts(host, client_name):
    miarec_apps.assert_rest_api_rejects(host, GROUP, PORT, client_name)


@needs_tls
@pytest.mark.parametrize("component, ca_file", [
    ("database", f"{MIAREC_TLS_DIR}/db-ca.crt"),
    ("redis", f"{MIAREC_TLS_DIR}/redis-ca.crt"),
])
def test_untrusted_ca_breaks_the_connection(host, component, ca_file):
    miarec_apps.assert_untrusted_ca_breaks(host, PORT, SERVICE, ca_file, component)
