"""Route policy: who may reach the server over which network, and what each route may do.

The peer address is the only identity the network layer trusts. These tests drive the real app with TestClient under
different peer addresses (the TCP peer a phone on iBus, the hotspot, a tailnet or a relay would present).
"""
from __future__ import annotations

import json
import shutil
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "services/api"), str(ROOT / "contracts/src")]

from app import database as db, main, network_policy as net, security, settings, tickets  # noqa: E402
from app.discovery import REPLIES, DiscoveryProtocol  # noqa: E402

IBUS = ("10.12.253.129", 50001)
HOTSPOT = ("10.11.229.63", 50002)
TAILNET = ("100.101.102.103", 50003)
STRANGER = ("192.168.50.9", 50004)
RELAY_PEER = ("10.66.0.1", 50005)
LOGIN = {"username": "admin1@safespace.com", "password": "admin123", "device_name": "t", "client_type": "mobile"}


def make_policy(monkeypatch, mode="ibus", **env):
    monkeypatch.setenv("NETWORK_MODE", mode)
    for key in ("TRUSTED_LAN_CIDRS", "IBUS_CIDRS", "TAILNET_CIDRS", "TRUSTED_PROXIES", "IBUS_PASSWORD_LOGIN"):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    net._POLICY.update(sig=None, policy=None, checked=0.0)
    return net.policy()


@pytest.fixture(autouse=True)
def reset_policy():
    net._POLICY.update(sig=None, policy=None, checked=0.0)
    REPLIES.clear()
    yield
    net._POLICY.update(sig=None, policy=None, checked=0.0)


@pytest.fixture
def storage(tmp_path, monkeypatch):
    for folder in ("media", "uploads", "logs", "recordings", "snapshots", "exports", "backups", "dist", "previews"):
        (tmp_path / folder).mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(settings, "STORAGE", tmp_path)
    monkeypatch.setattr(settings, "DB_PATH", tmp_path / "safespace.db")
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "safespace.db")
    monkeypatch.setattr(main, "STORAGE", tmp_path)
    monkeypatch.delenv("INITIAL_ADMIN_USERNAME", raising=False)
    monkeypatch.delenv("INITIAL_ADMIN_PASSWORD", raising=False)
    monkeypatch.setenv("SEED_ACCOUNTS", "admin1@safespace.com:admin123:Admin 1,admin2@safespace.com:admin123:Admin 2")
    main.ATTEMPTS.clear()
    tickets.TICKETS.clear()
    return tmp_path


def client_for(peer, https=True, headers=None):
    base = "https://testserver" if https else "http://testserver"
    return TestClient(main.app, base_url=base, client=peer, headers=headers or {})


# ---- classification ------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("peer,route", [
    ("127.0.0.1", "loopback"), ("::1", "loopback"), ("testclient", "loopback"), ("::ffff:127.0.0.1", "loopback"),
    ("10.11.229.63", "trusted_lan"), ("10.12.253.129", "ibus_lan"), ("::ffff:10.12.0.7", "ibus_lan"),
    ("100.101.102.103", "tailnet"),
])
def test_peer_address_decides_the_route(monkeypatch, peer, route):
    p = make_policy(monkeypatch, "anywhere")
    assert p.classify(peer, {}, "https", "x").route == route


@pytest.mark.parametrize("peer", ["192.168.1.50", "8.8.8.8", "not-an-ip", "", None])
def test_unknown_networks_are_refused(monkeypatch, peer):
    result = make_policy(monkeypatch, "anywhere").classify(peer, {}, "https", "x")
    assert not result.allowed and result.route is None


def test_modes_enable_routes(monkeypatch):
    hot = make_policy(monkeypatch, "hotspot_only")
    assert hot.classify("10.11.229.63", {}, "http").allowed
    assert not hot.classify("10.12.253.129", {}, "https").allowed       # the original lock, still available
    assert not hot.classify("100.101.102.103", {}, "http").allowed
    ibus = make_policy(monkeypatch, "ibus")
    assert ibus.classify("10.12.253.129", {}, "https").allowed
    assert ibus.classify("100.101.102.103", {}, "http").allowed
    assert not ibus.classify("10.66.0.1", {}, "https").allowed           # no relay unless mode=anywhere
    with pytest.raises(ValueError):
        make_policy(monkeypatch, "everywhere")


def test_ibus_requires_tls_but_hotspot_does_not(monkeypatch):
    p = make_policy(monkeypatch, "ibus")
    plain = p.classify("10.12.253.129", {}, "http")
    assert not plain.allowed and "encrypted" in plain.reason
    assert p.classify("10.12.253.129", {}, "https").allowed
    assert p.classify("10.11.229.63", {}, "http").allowed
    assert p.classify("10.12.253.129", {}, "http", enforce_tls=False).allowed   # discovery is UDP: no scheme


def test_env_extends_the_configured_networks(monkeypatch):
    p = make_policy(monkeypatch, "ibus", TRUSTED_LAN_CIDRS="192.168.1.0/24", IBUS_CIDRS="172.20.0.0/16")
    assert p.classify("192.168.1.77", {}, "http").route == "trusted_lan"
    assert p.classify("172.20.4.4", {}, "https").route == "ibus_lan"


def test_forwarding_headers_are_never_trusted_from_ordinary_peers(monkeypatch):
    p = make_policy(monkeypatch, "anywhere", TRUSTED_PROXIES="10.66.0.1")
    spoof = {"x-forwarded-for": "10.11.229.5", "x-forwarded-proto": "https"}
    ibus = p.classify("10.12.253.129", spoof, "http")
    assert ibus.client_ip == "10.12.253.129" and not ibus.allowed       # header ignored; still plain http on iBus
    assert not p.classify("127.0.0.1", spoof, "http").allowed          # unknown local proxy: refuse, don't trust "loopback"


def test_relay_peer_gets_the_forwarded_client_scheme_and_host(monkeypatch):
    p = make_policy(monkeypatch, "anywhere", TRUSTED_PROXIES="10.66.0.1")
    c = p.classify("10.66.0.1", {"x-forwarded-for": "203.0.113.9, 10.66.0.1", "x-forwarded-proto": "https",
                                 "x-forwarded-host": "safespace.example.com"}, "http", "10.66.0.2:8000")
    assert (c.route, c.client_ip, c.scheme, c.host, c.allowed) == ("relay", "203.0.113.9", "https", "safespace.example.com", True)
    assert not c.caps.password_login and not c.caps.enroll and c.caps.ladder == "reduced"
    assert not p.classify("10.66.0.1", {"x-forwarded-proto": "https"}, "http").allowed            # relay forgot the client
    assert not p.classify("10.66.0.1", {"x-forwarded-for": "garbage", "x-forwarded-proto": "https"}, "http").allowed
    assert not p.classify("10.66.0.1", {"x-forwarded-for": "203.0.113.9"}, "http").allowed        # relay over plain http


def test_ibus_password_login_can_be_relaxed_explicitly(monkeypatch):
    assert not make_policy(monkeypatch, "ibus").caps["ibus_lan"].password_login
    assert make_policy(monkeypatch, "ibus", IBUS_PASSWORD_LOGIN="true").caps["ibus_lan"].password_login


# ---- the real app under different peers ------------------------------------------------------------------------------

def test_ibus_peer_is_encrypted_and_token_only(storage, monkeypatch):
    make_policy(monkeypatch, "ibus")
    with client_for(IBUS, https=False) as plain:
        refused = plain.get("/api/v1/health/live")
        assert refused.status_code == 403 and "encrypted" in refused.json()["detail"]
    with client_for(IBUS) as ibus:
        assert ibus.get("/api/v1/health/live").status_code == 200
        identity = ibus.get("/api/v1/health/identity", params={"nonce": "n1"}).json()
        assert identity["route"] == "ibus_lan" and identity["route_capabilities"]["password_login"] is False
        assert identity["proof"] == net.identity_proof("n1")
        denied = ibus.post("/api/v1/auth/login", json=LOGIN)
        assert denied.status_code == 403 and "Pair this device" in denied.json()["detail"]
        # refused before the body is even validated, so an attacker learns nothing from a 422
        assert ibus.post("/api/v1/devices/enroll", json={"installation_id": "x"}).status_code == 403
        assert ibus.get("/api/v1/auth/seed-accounts").json()["accounts"] == []
        assert ibus.get("/api/v1/internal/cameras").status_code == 404
        assert ibus.get("/api/v1/events").status_code == 401


def test_stranger_network_gets_nothing_not_even_health(storage, monkeypatch):
    make_policy(monkeypatch, "ibus")
    with client_for(STRANGER) as stranger:
        for path in ("/api/v1/health/live", "/api/v1/health/identity", "/api/v1/auth/seed-accounts"):
            assert stranger.get(path).status_code == 403


def test_hotspot_and_tailnet_keep_password_login(storage, monkeypatch):
    make_policy(monkeypatch, "ibus")
    for peer in (HOTSPOT, TAILNET):
        with client_for(peer, https=False) as phone:
            assert phone.post("/api/v1/auth/login", json=LOGIN).status_code == 200
            assert len(phone.get("/api/v1/auth/seed-accounts").json()["accounts"]) == 2


def test_hotspot_only_mode_reproduces_the_original_lock(storage, monkeypatch):
    make_policy(monkeypatch, "hotspot_only")
    with client_for(IBUS) as ibus:
        assert ibus.get("/api/v1/health/live").status_code == 403
    with client_for(HOTSPOT, https=False) as hotspot:
        assert hotspot.get("/api/v1/health/live").status_code == 200


def test_client_supplied_wifi_names_are_not_a_credential(storage, monkeypatch):
    make_policy(monkeypatch, "hotspot_only")
    claim = {"X-SafeSpace-Wifi-SSID": "Nothing Phone (4a)_7495", "X-SafeSpace-Wifi-BSSID": "6a:8a:00:6e:32:b1"}
    with client_for(IBUS, headers=claim) as ibus:
        assert ibus.get("/api/v1/health/live").status_code == 403       # claiming the hotspot SSID does not help
    with client_for(HOTSPOT, https=False, headers={"X-SafeSpace-Wifi-SSID": "SomethingElse"}) as hotspot:
        assert hotspot.get("/api/v1/health/live").status_code == 200    # and a wrong claim does not hurt


def test_pairing_link_gives_a_camera_phone_only_a_camera_token(storage, monkeypatch):
    make_policy(monkeypatch, "ibus")
    with client_for(("127.0.0.1", 50010), https=False) as laptop:
        admin = laptop.post("/api/v1/auth/login", json={**LOGIN, "installation_id": "laptop-0001"}).json()["device_token"]
        made = laptop.post("/api/v1/auth/pairing-code", json={"role": "camera"}, headers={"Authorization": f"Bearer {admin}"}).json()
        assert made["link"].startswith("safespace://pair?") and f"c={made['code']}" in made["link"] and "r=camera" in made["link"]
    with client_for(IBUS) as phone:
        paired = phone.post("/api/v1/auth/pair", json={"code": made["code"], "device_name": "Door", "installation_id": "phone-0001"})
        assert paired.status_code == 200
        body = paired.json()
        assert body["scope"] == "camera" and body["camera_id"].startswith("cam_")
        token = {"Authorization": f"Bearer {body['device_token']}"}
        assert phone.get("/api/v1/events", headers=token).status_code == 403
        assert phone.get("/api/v1/devices/me", headers=token).json()["device"]["route"] == "ibus_lan"
        assert phone.post("/api/v1/auth/pair", json={"code": made["code"], "device_name": "x", "installation_id": "phone-0002"}).status_code == 401


def test_pairing_link_for_a_control_phone_gives_an_admin_token(storage, monkeypatch):
    make_policy(monkeypatch, "ibus")
    with client_for(("127.0.0.1", 50011), https=False) as laptop:
        admin = laptop.post("/api/v1/auth/login", json=LOGIN).json()["device_token"]
        code = laptop.post("/api/v1/auth/pairing-code", json={}, headers={"Authorization": f"Bearer {admin}"}).json()["code"]
    with client_for(IBUS) as phone:
        paired = phone.post("/api/v1/auth/pair", json={"code": code, "device_name": "Admin phone", "installation_id": "phone-ctl-1"}).json()
        assert paired["scope"] == "admin" and paired["role"] == "control"
        assert phone.get("/api/v1/events", headers={"Authorization": f"Bearer {paired['device_token']}"}).status_code == 200


def test_login_throttle_counts_the_real_client_behind_a_relay(storage, monkeypatch):
    make_policy(monkeypatch, "anywhere", TRUSTED_PROXIES="10.66.0.1", )
    # password login is off on the relay, but the throttle also guards /auth/pair: attackers are told apart by real address
    def attempt(client, who):
        return client.post("/api/v1/auth/pair", json={"code": "ABCD1234", "device_name": "x"},
                           headers={"X-Forwarded-For": who, "X-Forwarded-Proto": "https", "X-Forwarded-Host": "safespace.example.com"})
    with client_for(RELAY_PEER, https=False) as relay:
        assert [attempt(relay, "203.0.113.9").status_code for _ in range(10)] == [401] * 10
        assert attempt(relay, "203.0.113.9").status_code == 429          # that client is locked out ...
        assert attempt(relay, "198.51.100.7").status_code == 401         # ... but not everyone else behind the relay


# ---- tickets and sockets -------------------------------------------------------------------------------------------------

def test_ws_tickets_are_single_use_and_event_socket_is_admin_only(storage, monkeypatch):
    make_policy(monkeypatch, "ibus")
    with client_for(HOTSPOT, https=False) as phone:
        admin = phone.post("/api/v1/auth/login", json=LOGIN).json()["device_token"]
        ticket = phone.post("/api/v1/ws-tickets", headers={"Authorization": f"Bearer {admin}"}).json()["ticket"]
        with phone.websocket_connect(f"/api/v1/ws?ticket={ticket}") as ws:
            assert ws.receive_json()["type"] == "hello"
        with pytest.raises(Exception):
            with phone.websocket_connect(f"/api/v1/ws?ticket={ticket}"):
                pass                                                       # already used
        code = phone.post("/api/v1/auth/pairing-code", json={"role": "camera"}, headers={"Authorization": f"Bearer {admin}"}).json()["code"]
        cam = phone.post("/api/v1/auth/pair", json={"code": code, "device_name": "c", "installation_id": "cam-ticket-1"}).json()
        cam_ticket = phone.post("/api/v1/ws-tickets", headers={"Authorization": f"Bearer {cam['device_token']}"}).json()["ticket"]
        with pytest.raises(Exception):
            with phone.websocket_connect(f"/api/v1/ws?ticket={cam_ticket}"):
                pass                                                       # a camera token never gets the alert feed


def test_camera_token_may_publish_only_its_own_camera(storage, monkeypatch):
    make_policy(monkeypatch, "ibus")
    with client_for(HOTSPOT, https=False) as phone:
        admin = phone.post("/api/v1/auth/login", json=LOGIN).json()["device_token"]
        code = phone.post("/api/v1/auth/pairing-code", json={"role": "camera"}, headers={"Authorization": f"Bearer {admin}"}).json()["code"]
        cam = phone.post("/api/v1/auth/pair", json={"code": code, "device_name": "c", "installation_id": "cam-own-1"}).json()
        headers = {"Authorization": f"Bearer {cam['device_token']}"}
        with phone.websocket_connect(f"/api/v1/cameras/{cam['camera_id']}/publish", headers=headers) as ws:
            assert ws.receive_json()["type"] == "ready"
        with pytest.raises(Exception):
            with phone.websocket_connect("/api/v1/cameras/cam_someone_else/publish", headers=headers):
                pass
        with pytest.raises(Exception):                                     # and it cannot watch
            with phone.websocket_connect(f"/api/v1/cameras/{cam['camera_id']}/view", headers=headers):
                pass


def test_ibus_socket_must_be_wss(storage, monkeypatch):
    make_policy(monkeypatch, "ibus")
    with client_for(IBUS) as secure:
        admin_code = None   # no credentials needed: the handshake is refused (4401) rather than the route (4403) over wss
        with pytest.raises(Exception):
            with secure.websocket_connect("/api/v1/cameras/cam_x/view"):
                pass
    with TestClient(main.app, base_url="http://testserver", client=IBUS) as plain:
        with pytest.raises(Exception):
            with plain.websocket_connect("/api/v1/cameras/cam_x/view"):
                pass


# ---- discovery -----------------------------------------------------------------------------------------------------------

def discover(sender, **extra):
    payload = {"op": "discover", "app": "safespace", "v": 1, **extra}
    return DiscoveryProtocol().reply_for(json.dumps(payload).encode(), sender)


def test_discovery_is_open_on_the_hotspot_and_authenticated_on_ibus(monkeypatch):
    make_policy(monkeypatch, "ibus")
    open_reply = discover("10.11.229.63")
    assert open_reply and json.loads(open_reply)["op"] == "announce"
    assert discover("10.12.253.129") is None                                   # no proof: the server stays silent
    ts = int(time.time())
    good = discover("10.12.253.129", ts=ts, proof=net.discovery_proof(ts))
    assert good and json.loads(good)["route"] == "ibus_lan"
    assert discover("10.12.253.130", ts=ts, proof="0" * 64) is None
    stale = ts - 600
    assert discover("10.12.253.131", ts=stale, proof=net.discovery_proof(stale)) is None
    assert discover("192.168.50.9", ts=ts, proof=net.discovery_proof(ts)) is None   # unknown network, even with the secret
    assert discover("100.101.102.103") is None                                 # tailnet is reached by name, not broadcast
    assert DiscoveryProtocol().reply_for(b"\xff\xfe not json", "10.11.229.63") is None


def test_discovery_reply_is_signed_and_limited_to_the_senders_network(monkeypatch):
    make_policy(monkeypatch, "ibus")
    net.set_listeners(8000, 8443, ["PIN"])
    monkeypatch.setattr(net, "local_ipv4", lambda: [("Wi-Fi", "10.12.253.133"), ("Hotspot", "10.11.229.33")])
    reply = json.loads(discover("10.11.229.63"))
    assert {r["route"] for r in reply["routes"]} <= {"trusted_lan", "configured"}
    assert json.loads(reply["routes_json"]) == {"server_id": reply["server_id"], "routes": reply["routes"], "pins": reply["pins"]}
    assert reply["routes_sig"] == net.routes_signature(reply["routes_json"])
    net.set_listeners(settings.HTTP_PORT, None, [])


def test_discovery_replies_are_rate_limited(monkeypatch):
    make_policy(monkeypatch, "ibus")
    answers = [discover("10.11.229.63") is not None for _ in range(12)]
    assert answers[:5] == [True] * 5 and not any(answers[5:])


# ---- advertised routes and the TLS key pin ---------------------------------------------------------------------------------

def test_advertised_routes_follow_the_laptops_live_addresses(monkeypatch):
    make_policy(monkeypatch, "ibus")
    net.set_listeners(8000, 8443, ["PIN"])
    monkeypatch.setattr(net, "local_ipv4", lambda: [("Wi-Fi", "10.12.253.133"), ("Ethernet", "192.168.9.4"), ("Hotspot", "10.11.229.33")])
    urls = {(r["route"], r["url"]) for r in net.advertised_routes()}
    assert ("ibus_lan", "https://10.12.253.133:8443") in urls
    assert ("ibus_lan", "http://10.12.253.133:8000") not in urls          # iBus never gets a plain URL
    assert ("trusted_lan", "http://10.11.229.33:8000") in urls and ("trusted_lan", "https://10.11.229.33:8443") in urls
    assert not any("192.168.9.4" in url for _, url in urls)               # an unconfigured network is not advertised
    net.set_listeners(settings.HTTP_PORT, None, [])


@pytest.mark.skipif(shutil.which("openssl") is None and not Path(r"C:\Program Files\Git\mingw64\bin\openssl.exe").exists(), reason="openssl not available")
def test_certificate_pin_is_stable_when_only_the_addresses_change(tmp_path, monkeypatch):
    from app import tls
    first = tls.ensure_all(tmp_path, extra_sans=["10.1.1.1"])
    again = tls.ensure_all(tmp_path, extra_sans=["10.1.1.1"])
    assert first.regenerated and not again.regenerated and first.pin == again.pin
    moved = tls.ensure_all(tmp_path, extra_sans=["10.2.2.2"])               # the laptop got a new DHCP address
    assert moved.regenerated and moved.pin == first.pin                      # new certificate, same key, same pin
    assert "IP:10.2.2.2" in moved.sans


def test_a_control_phone_learns_its_camera_id_when_it_pairs(storage, monkeypatch):
    """So a phone paired as a control phone can also be used as a camera without pairing again."""
    make_policy(monkeypatch, "ibus")
    with client_for(("127.0.0.1", 50020), https=False) as laptop:
        admin = laptop.post("/api/v1/auth/login", json=LOGIN).json()["device_token"]
        code = laptop.post("/api/v1/auth/pairing-code", json={}, headers={"Authorization": f"Bearer {admin}"}).json()["code"]
        paired = laptop.post("/api/v1/auth/pair", json={"code": code, "device_name": "Phone", "installation_id": "phone-cam-id-1"}).json()
    assert paired["camera_id"] == security.stable_camera_id("phone-cam-id-1")
