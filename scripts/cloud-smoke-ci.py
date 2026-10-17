"""CI-only HTTPS-origin behavior smoke for the cloud Docker image.

The Docker process and PostgreSQL service live on one disposable GitHub runner.
All access credentials are generated in CI and never printed.
"""
import json
import subprocess
import sys
import time
from http.client import HTTPConnection
from urllib.parse import urlencode


def read_ci_env(filename: str) -> dict[str, str]:
    config = {}
    with open(filename, encoding="utf-8") as file:
        for line in file:
            k, v = line.rstrip("\n").split("=", 1)
            config[k] = v
    return config


def request(method: str, path: str, *, body: bytes | None = None, headers=None):
    conn = HTTPConnection("127.0.0.1", 18080, timeout=4)
    try:
        conn.request(method, path, body=body, headers=headers or {})
        response = conn.getresponse()
        return response.status, {k.lower(): v for k, v in response.getheaders()}, response.read()
    finally:
        conn.close()


def wait_for_health():
    for _ in range(50):
        try:
            status, _, data = request("GET", "/health")
            if status == 200 and json.loads(data)["status"] == "ok":
                return
        except (OSError, ValueError):
            pass
        time.sleep(1)
    raise AssertionError("Cloud Docker entrypoint did not become healthy")


def main():
    config = read_ci_env(sys.argv[1])
    role_tokens = json.loads(config["HANDOFFGUARD_AUTH_TOKENS"])
    sales = next(k for k, v in role_tokens.items() if v["role"] == "sales")

    wait_for_health()
    status, headers, _ = request("GET", "/")
    assert status == 302 and headers.get("location") == "/demo/login", status
    status, _, _ = request("GET", "/api/v1/orders/not-found",
                           headers={"Authorization": "Bearer " + sales})
    assert status == 401, status
    status, _, html = request("GET", "/demo/login")
    assert status == 200 and b"Reviewer access key" in html, status

    body = urlencode({"access_key": config["HANDOFFGUARD_DEMO_ACCESS_KEY"]}).encode()
    status, headers, _ = request("POST", "/demo/login", body=body,
                                headers={"Content-Type": "application/x-www-form-urlencoded"})
    assert status == 303 and "set-cookie" in headers, status
    cookie = headers["set-cookie"].split(";", 1)[0]

    status, _, frontend = request("GET", "/", headers={"Cookie": cookie})
    assert status == 200 and b"html" in frontend.lower(), status

    status, _, no_role = request("GET", "/api/v1/orders/not-found",
                                 headers={"Cookie": cookie})
    assert status == 401 and b"Bearer token required" in no_role, status

    status, _, created = request(
        "POST", "/api/v1/orders",
        body=json.dumps({
            "product_code": "SYNTHETIC-CLOUD-CI",
            "quantity": 100,
            "unit_sales_price_kopeks": 100000,
            "unit_est_cost_kopeks": 60000,
            "delivery_date": "2026-11-12",
            "approved_source_id": "cloud-ci-synthetic",
        }).encode(),
        headers={
            "Cookie": cookie,
            "Authorization": "Bearer " + sales,
            "Content-Type": "application/json",
        },
    )
    assert status == 201, (status, created[:300])
    order_id = json.loads(created)["id"]

    subprocess.run(["docker", "restart", "handoffguard-cloud-ci"],
                   check=True, stdout=subprocess.DEVNULL)
    wait_for_health()
    status, _, reopened = request(
        "GET", "/api/v1/orders/" + order_id,
        headers={"Cookie": cookie, "Authorization": "Bearer " + sales},
    )
    assert status == 200, (status, reopened[:300])
    assert json.loads(reopened)["revision"] == 1
    assert json.loads(reopened)["quantity"] == 100
    print("PASS: packaged cloud Docker image, private reviewer gate, "
          "role auth and persistent PostgreSQL order across container restart")


if __name__ == "__main__":
    main()
