"""Screen tier: the screen recording controller.

The screen controller has its own TLS files (vars/screen.yml), apart from
the recorder's, so a changed file restarts both services on a shared host.
"""
import pytest
import miarec_apps
from conftest import hosts_in, process_owners, listening_on_all_interfaces, needs_tls, \
    MIAREC_SCREEN_TLS_DIR, MIAREC_SCREEN_VERSION, SCREEN_REST_PORT

testinfra_hosts = hosts_in('screen')

GROUP = "screen"
SERVICE = "miarec_screen"
PORT = SCREEN_REST_PORT


def test_service(host):
    s = host.service(SERVICE)
    assert s.is_enabled
    assert s.is_running


def test_process_user(host):
    assert process_owners(host, "miarec_screen") == {("miarec", "miarec")}


def test_listening(host):
    # REST API, and the client connections over TCP and TLS
    for port in [PORT, 6091, 6092]:
        assert listening_on_all_interfaces(host, port), f"The screen controller does not listen on port {port}"


def test_health_endpoint(host):
    miarec_apps.assert_health_from_web(host, GROUP, PORT)


def test_registered_in_database(host):
    miarec_apps.assert_registered(host, "modules", "app_type = 'screen_rec'", "miarec_screen")


def test_db_connections_use_tls(host):
    miarec_apps.assert_db_connections(host, GROUP)


@pytest.mark.parametrize("client_group", miarec_apps.REST_CLIENT_GROUPS)
def test_rest_api_allows_miarecweb(host, client_group):
    miarec_apps.assert_rest_api_allows(host, GROUP, PORT, client_group, MIAREC_SCREEN_VERSION)


@pytest.mark.parametrize("client_name", miarec_apps.other_hosts_params(GROUP))
def test_rest_api_rejects_other_hosts(host, client_name):
    miarec_apps.assert_rest_api_rejects(host, GROUP, PORT, client_name)


@needs_tls
@pytest.mark.parametrize("component, ca_file", [
    ("database", f"{MIAREC_SCREEN_TLS_DIR}/db-ca.crt"),
    ("redis", f"{MIAREC_SCREEN_TLS_DIR}/redis-ca.crt"),
])
def test_untrusted_ca_breaks_the_connection(host, component, ca_file):
    miarec_apps.assert_untrusted_ca_breaks(host, PORT, SERVICE, ca_file, component)
