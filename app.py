from pymongo import MongoClient
import os
from flask import Flask, request, jsonify
from cerberus import Validator

app = Flask(__name__)

# Connect to MongoDB
mongo_uri = os.getenv('MONGO_URI', 'mongodb://mongo:27017/')
client = MongoClient(mongo_uri)
db = client['Final']

# Collections from the database
goods_collection = db["goods"]

# Initialize the schema validator for Cerberus
good_schema = {
    "name": {"type": "string", "minlength": 1, "maxlength": 100},
    "category": {"type": "string", "minlength": 1, "maxlength": 100},
    "price_per_item": {"type": "float", "min": 0.01},
    "description": {"type": "string", "maxlength": 500},
    "stock_count": {"type": "integer", "min": 0}
}
validator = Validator(good_schema)


# Display
@app.route('/')
def hello():
    return "Service 2!"


# Goods API: Add new goods
@app.route('/inventory/add', methods=['POST'])
def add_goods():
    data = request.get_json()

    # Validate input using Cerberus
    if not validator.validate(data):
        return jsonify({"error": "Invalid data", "details": validator.errors}), 400

    # Check for duplicate goods
    if goods_collection.find_one({"name": data["name"]}):
        return jsonify({"error": "A good with this name already exists"}), 400

    # Insert the new item into the inventory
    try:
        new_good = {
            "name": data["name"],
            "category": data["category"],
            "price_per_item": data["price_per_item"],
            "description": data["description"],
            "stock_count": data["stock_count"]
        }
        goods_collection.insert_one(new_good)
        return jsonify({"message": "Good added successfully"}), 201
    except Exception as e:
        return jsonify({"error": "Failed to add good", "details": str(e)}), 500


# API: Deduct goods from stock
@app.route('/inventory/deduct/<string:good_name>', methods=['PATCH'])
def deduct_goods(good_name):
    data = request.get_json()
    quantity = data.get("quantity", 1)  # Default to deducting 1 item

    # Validate quantity
    if not isinstance(quantity, int) or quantity <= 0:
        return jsonify({"error": "'quantity' must be a positive integer"}), 400

    # Fetch the good from the database
    good = goods_collection.find_one({"name": good_name})
    if not good:
        return jsonify({"error": "Good not found"}), 404

    if good["stock_count"] < quantity:
        return jsonify({"error": "Not enough stock available"}), 400

    # Deduct the stock
    try:
        result = goods_collection.update_one(
            {"name": good_name, "stock_count": {"$gte": quantity}},
            {"$inc": {"stock_count": -quantity}}
        )
        if result.matched_count == 0:
            return jsonify({"error": "Not enough stock available"}), 400

        return jsonify({"message": f"{quantity} item(s) deducted from '{good_name}' stock"}), 200
    except Exception as e:
        return jsonify({"error": "Failed to deduct stock", "details": str(e)}), 500


# API: Update goods details
@app.route('/inventory/update/<string:good_name>', methods=['PATCH'])
def update_goods(good_name):
    data = request.get_json()

    # Check if the good exists
    good = goods_collection.find_one({"name": good_name})
    if not good:
        return jsonify({"error": "Good not found"}), 404

    # Validate and update fields
    updated_fields = {}
    allowed_fields = ["name", "category", "price_per_item", "description", "stock_count"]
    for field, value in data.items():
        if field in allowed_fields:
            if field == "price_per_item" and (not isinstance(value, (int, float)) or value <= 0):
                return jsonify({"error": "'price_per_item' must be a positive number"}), 400
            if field == "stock_count" and (not isinstance(value, int) or value < 0):
                return jsonify({"error": "'stock_count' must be a non-negative integer"}), 400
            updated_fields[field] = value

    if updated_fields:
        try:
            goods_collection.update_one({"name": good_name}, {"$set": updated_fields})
            return jsonify({"message": "Good updated successfully", "updated_fields": updated_fields}), 200
        except Exception as e:
            return jsonify({"error": "Failed to update good", "details": str(e)}), 500
    else:
        return jsonify({"error": "No valid fields to update"}), 400


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5002)
