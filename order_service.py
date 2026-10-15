"""Order Service: owns orders and queries Inventory before creating one."""

import os
import uuid

import requests
from flask import Flask, jsonify, request


app = Flask(__name__)

# Sample order data owned exclusively by the Order Service.
ORDERS: dict[str, dict] = {}


def inventory_url() -> str:
    return os.getenv("INVENTORY_URL", "http://127.0.0.1:5001/inventory/check")


def inventory_timeout() -> float:
    return float(os.getenv("INVENTORY_TIMEOUT_SECONDS", "1"))


@app.get("/health")
def health():
    return jsonify(service="order", status="ok"), 200


@app.get("/orders/<order_id>")
def get_order(order_id: str):
    order = ORDERS.get(order_id)
    if order is None:
        return jsonify(error="order not found"), 404
    return jsonify(order), 200


@app.post("/orders")
def create_order():
    """Handle CreateOrder after synchronously querying Inventory."""
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(error="request body must be a JSON object"), 400

    item_id = payload.get("item_id")
    quantity = payload.get("quantity")
    customer_id = payload.get("customer_id", "demo-customer")

    if not isinstance(item_id, str) or not item_id.strip():
        return jsonify(error="item_id must be a non-empty string"), 400
    if not isinstance(quantity, int) or isinstance(quantity, bool) or quantity <= 0:
        return jsonify(error="quantity must be a positive integer"), 400
    if not isinstance(customer_id, str) or not customer_id.strip():
        return jsonify(error="customer_id must be a non-empty string"), 400

    try:
        inventory_response = requests.get(
            inventory_url(),
            params={"item_id": item_id, "quantity": quantity},
            timeout=inventory_timeout(),
        )
    except requests.exceptions.Timeout:
        app.logger.warning("Inventory query timed out")
        return (
            jsonify(
                error="inventory_timeout",
                message="Inventory Service did not respond before the timeout",
                order_status="not_created",
            ),
            504,
        )
    except requests.exceptions.ConnectionError:
        app.logger.warning("Inventory Service is unavailable")
        return (
            jsonify(
                error="inventory_unavailable",
                message="Order could not be created because Inventory Service is unavailable",
                order_status="not_created",
            ),
            503,
        )

    try:
        inventory_result = inventory_response.json()
    except requests.exceptions.JSONDecodeError:
        return (
            jsonify(
                error="invalid_inventory_response",
                message="Inventory Service returned an invalid response",
                order_status="not_created",
            ),
            502,
        )

    if inventory_response.status_code == 404:
        return (
            jsonify(
                error="item_not_found",
                inventory=inventory_result,
                order_status="rejected",
            ),
            404,
        )

    if inventory_response.status_code != 200:
        return (
            jsonify(
                error="inventory_query_failed",
                inventory=inventory_result,
                order_status="not_created",
            ),
            502,
        )

    if not inventory_result.get("available"):
        return (
            jsonify(
                error="insufficient_inventory",
                inventory=inventory_result,
                order_status="rejected",
            ),
            409,
        )

    order_id = str(uuid.uuid4())
    order = {
        "customer_id": customer_id,
        "item_id": item_id,
        "order_id": order_id,
        "quantity": quantity,
        "status": "created",
    }
    ORDERS[order_id] = order

    # In a production design, commit the order and publish OrderCreated
    # atomically through a transactional outbox.
    app.logger.info("OrderCreated event: %s", order_id)
    return jsonify(order), 201


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="127.0.0.1", port=port, threaded=True)
