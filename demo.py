"""Run successful, unavailable-item, and dependency-failure scenarios."""

from contextlib import contextmanager
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

import requests


ROOT = Path(__file__).resolve().parent


@contextmanager
def service(script_name: str, environment: dict[str, str]):
    environment_copy = os.environ.copy()
    environment_copy.update(environment)
    process = subprocess.Popen(
        [sys.executable, str(ROOT / script_name)],
        cwd=ROOT,
        env=environment_copy,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        yield process
    finally:
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()


def wait_for_port(port: int, timeout: float = 8) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket() as connection:
            connection.settimeout(0.2)
            if connection.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.1)
    raise RuntimeError(f"service on port {port} did not start")


def show(label: str, response: requests.Response) -> None:
    print(f"{label}: HTTP {response.status_code}")
    print(json.dumps(response.json(), indent=2, sort_keys=True))


def main() -> None:
    order_environment = {
        "PORT": "5200",
        "INVENTORY_URL": "http://127.0.0.1:5201/inventory/check",
        "INVENTORY_TIMEOUT_SECONDS": "1",
    }

    print("=== DISTRIBUTED STORE DEMO ===")
    with service("order_service.py", order_environment):
        wait_for_port(5200)

        with service("inventory_service.py", {"PORT": "5201"}):
            wait_for_port(5201)
            show(
                "Successful order",
                requests.post(
                    "http://127.0.0.1:5200/orders",
                    json={
                        "customer_id": "customer-101",
                        "item_id": "book",
                        "quantity": 2,
                    },
                    timeout=3,
                ),
            )
            show(
                "Unavailable quantity",
                requests.post(
                    "http://127.0.0.1:5200/orders",
                    json={
                        "customer_id": "customer-102",
                        "item_id": "laptop",
                        "quantity": 5,
                    },
                    timeout=3,
                ),
            )

        # Inventory is stopped here while Order remains running.
        show(
            "Inventory stopped",
            requests.post(
                "http://127.0.0.1:5200/orders",
                json={
                    "customer_id": "customer-103",
                    "item_id": "book",
                    "quantity": 1,
                },
                timeout=3,
            ),
        )
        show(
            "Order Service after dependency failure",
            requests.get("http://127.0.0.1:5200/health", timeout=3),
        )


if __name__ == "__main__":
    main()

