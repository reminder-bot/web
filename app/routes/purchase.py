import stripe
import json
from flask import jsonify, request, render_template

from app import app

from . import LOGO_URL


@app.route('/buy/')
def buy_page():
    return render_template('buy_page.html', title='Purchase', logo=LOGO_URL)


@app.route('/create_customer/', methods=['POST'])
def create_customer():
    data = json.loads(request.data)

    try:
        customer = stripe.Customer.create(
            email=data['email']
        )

        return jsonify(
            customer=customer
        )

    except Exception as e:
        return jsonify(error=str(e)), 400
