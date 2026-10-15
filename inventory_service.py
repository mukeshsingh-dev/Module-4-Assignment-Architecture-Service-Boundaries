"""Inventory Service: owns stock data and answers availability queries."""

import os

from flask import Flask, jsonify, request


app = Flask(__name__)

# Sample data owned exclusively by the Inventory Service.
INVENTORY = {
    "book": 10,
    "headphones": 4,
    "laptop": 2,
}


@app.get("/health")
def health():
    return jsonify(service="inventory", status="ok"), 200


@app.get("/inventory/check")
def check_inventory():
    """Answer a read-only availability query."""
    item_id = request.args.get("item_id", "").strip()
    quantity_text = request.args.get("quantity", "")

    if not item_id:
        return jsonify(error="item_id is required"), 400

    try:
        quantity = int(quantity_text)
    except ValueError:
        return jsonify(error="quantity must be a positive integer"), 400

    if quantity <= 0:
        return jsonify(error="quantity must be a positive integer"), 400

    if item_id not in INVENTORY:
        return (
            jsonify(
                available=False,
                available_quantity=0,
                item_id=item_id,
                message="item does not exist",
            ),
            404,
        )

    available_quantity = INVENTORY[item_id]
    return (
        jsonify(
            available=quantity <= available_quantity,
            available_quantity=available_quantity,
            item_id=item_id,
            message=(
                "inventory is available"
                if quantity <= available_quantity
                else "requested quantity is unavailable"
            ),
        ),
        200,
    )


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5001"))
    app.run(host="127.0.0.1", port=port, threaded=True)

