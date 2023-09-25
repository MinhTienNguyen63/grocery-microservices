from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
import requests
import pickle
from sqlalchemy.types import PickleType

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///carts.sqlite'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

PRODUCT_SERVICE_URL = 'http://127.0.0.1:5000/products/'


# Create a new CustomPickleType that uses a fixed protocol.
class CustomPickleType(PickleType):
    def __init__(self, protocol=4, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.protocol = protocol

    def _serialize(self, value):
        if value is None:
            return None
        return pickle.dumps(value, protocol=self.protocol)


# Cart Model
class Cart(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String, unique=True, nullable=False)
    items = db.Column(CustomPickleType, nullable=False, default={})

    def get_total_price(self):
        total = 0
        for product_id, quantity in self.items.items():
            product = requests.get(PRODUCT_SERVICE_URL + str(product_id)).json()
            if product:
                total += product['price'] * quantity
        return total


@app.route('/cart/<user_id>', methods=['GET'])
def get_cart(user_id):
    cart = Cart.query.filter_by(user_id=user_id).first()
    if not cart:
        return jsonify({"error": "Cart not found"}), 404

    cart_contents = {
        "user_id": cart.user_id,
        "items": cart.items,
        "total_price": cart.get_total_price()
    }
    return jsonify(cart_contents)


@app.route('/cart/<user_id>/add/<int:product_id>', methods=['POST'])
def add_to_cart(user_id, product_id):
    product = requests.get(PRODUCT_SERVICE_URL + str(product_id)).json()

    if 'error' in product:
        return jsonify({"error": product['error']}), 404

    quantity_to_add = request.json.get('quantity', 1)
    cart = Cart.query.filter_by(user_id=user_id).first()

    if not cart:
        cart = Cart(user_id=user_id)
        db.session.add(cart)

    if cart.items is None:
        cart.items = {}

    cart.items[product_id] = cart.items.get(product_id, 0) + quantity_to_add

    db.session.commit()

    return jsonify({
        "message": "Added to cart",
        "current_quantity": cart.items[product_id]
    })


@app.route('/cart/<user_id>/remove/<int:product_id>', methods=['POST'])
def remove_from_cart(user_id, product_id):
    quantity_to_remove = request.json.get('quantity', 1)
    cart = Cart.query.filter_by(user_id=user_id).first()

    if not cart:
        return jsonify({"error": "Cart not found"}), 404

    if product_id not in cart.items:
        return jsonify({"error": "Product not in cart"}), 404

    cart.items[product_id] -= quantity_to_remove
    if cart.items[product_id] <= 0:
        del cart.items[product_id]

    db.session.commit()

    return jsonify({
        "message": "Removed from cart",
        "remaining_quantity": cart.items.get(product_id, 0)
    })


if __name__ == '__main__':
    db.create_all()
    app.run(host='0.0.0.0', port=5001, debug=True)
