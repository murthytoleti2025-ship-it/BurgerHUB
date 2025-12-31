from flask import Flask, render_template, session, redirect, request
import pymongo
import datetime
import os.path
from bson import ObjectId
import re
import string
import time, datetime
import random
import os

my_client = pymongo.MongoClient("mongodb://localhost:27017")
my_db = my_client.get_database("BurgerHub")
app = Flask(__name__)
app.secret_key = "bh"
APP_ROOT = os.path.dirname(os.path.abspath(__file__))

admin_data = my_db["admin"]
customer_data = my_db["customer"]
delivery_data = my_db["delivery"]
product_data = my_db["item"]
product_category_data = my_db["item_category"]
order_data = my_db["order"]
payment_collection = my_db["payment"]
topping_data = my_db['topping']

@app.route("/")
def index():
    if "role" in session and session["role"] == "Admin":
        session["login_count"] = 0
        return redirect("/admin-home")
    elif "role" in session and session["role"] == "Delivery":
        session["login_count"] = 0
        return redirect("/delivery-home")
    elif "role" in session and session["role"] == "Customer":
        session["login_count"] = 0
        return redirect("/customer-home")
    products = product_data.find()
    categories = product_category_data.find({})
    message = request.args.get('message')
    if message:
        return render_template("index.html", products=products, getCategoryNameById=getCategoryNameById, message=message, categories=categories,is_product_in_cart=is_product_in_cart)
    return render_template("index.html", categories=categories, products=products, getCategoryNameById=getCategoryNameById, is_product_in_cart=is_product_in_cart)

# /add-to-plate
@app.route("/add-to-plate")
def add_to_cart():
    if "role" not in session:
        return redirect(
            "/login?message=Sign in or Sign up to get started with plate"
        )
    if session["role"] == "Customer":
        quantity = request.args.get("qty")
        product_id = request.args.get("product_id")
        product = product_data.find_one({'_id': ObjectId(product_id)})
        product_name = product['name']
        customer_id = session["customer_id"]
        selected_toppings = request.args.getlist('toppings[]')
        query = {"customer_id": ObjectId(customer_id), "status": "cart"}
        count = order_data.count_documents(query)

        query = {"customer_id": ObjectId(customer_id), "status": "cart", "items.product_id": product['_id']}
        existing_order = order_data.find_one(query)

        if existing_order:
            quantity = int(existing_order["items"][0]["quantity"]) + 1
            print(quantity)
            order_data.update_one(
                {
                    "_id": existing_order["_id"],
                    "status": "cart",
                    "items.product_id": product['_id'],
                },
                {"$set": {"items.$.quantity": quantity}},
            )
            return redirect("/view-plate")
        query = {"customer_id": ObjectId(customer_id), "status": "cart"}
        if count > 0:
            order = order_data.find_one(query)
            order_id = order["_id"]
            count = order_data.count_documents(
                {
                    "_id": ObjectId(order_id),
                    "status": "cart",
                    "items.product_id": ObjectId(product_id),
                }
            )
            if count > 0:
                order_data.update_one(
                    {
                        "_id": ObjectId(order_id),
                        "status": "cart",
                        "items.product_id": ObjectId(product_id),
                    },
                    {"$set": {"items.$.quantity": quantity}},
                )
            else:
                order_data.update_one(
                    {
                        "_id": ObjectId(order_id),
                        "status": "cart",
                    },
                    {
                        "$push": {
                            "items": {
                                "quantity": quantity,
                                "product_id": ObjectId(product_id),
                            },
                        }
                    },
                )
        else:
            product_to_cart = {"product_id": ObjectId(product_id), "quantity": 1}
            query = {
                "customer_id": ObjectId(customer_id),
                "status": "cart",
                "items": [product_to_cart],
                "delivery_type": 'delivery'
            }
            order_data.insert_one(query)
        operation = request.args.get('operation')
        if operation and operation == 'qty':
                return redirect("/view-plate")
        return redirect("/customer-home?message="+product_name+" Added to plate")

@app.route('/update-delivery-type', methods=['POST'])
def update_delivery_type():
    customer_id = session['customer_id']
    delivery_type = request.args.get('delivery_type')
    if order_data.count_documents({'customer_id':ObjectId(customer_id),'status':'cart'}) > 0:
        order = order_data.find_one({'customer_id':ObjectId(customer_id),'status':'cart'})
        order_data.update_one(
            { 
                "_id": ObjectId(order['_id'])
            },
            { 
                "$set": { "delivery_type": delivery_type } 
            } 
        )
    
    return redirect('/view_plate?message=changed delivery mode')  # Assuming view_plate is the endpoint for the view-plate page


@app.route("/login")
def login():
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/?message=Logout Successful!')

@app.route("/sign-up")
def sign_up():
    return render_template('sign-up.html')

@app.route("/admin-login")
def admin_login():
    return render_template('admin-login.html')

@app.route("/delivery-login")
def delivery_login():
    return render_template('delivery-login.html')

@app.route("/delivery-home")
def delivery_home():
    return render_template('delivery-home.html')

@app.route('/admin-home')
def admin_home():
    return render_template('admin-home.html')

@app.route('/customer-home')
def customer_home():
    message = request.args.get('message')
    cat_id = request.args.get('_id')
    products = product_data.find({})
    if cat_id:
        products = product_data.find({'category_id': ObjectId(cat_id)})
    categories = product_category_data.find({})
    return render_template('customer-home.html', products=products, categories=categories, getCategoryNameById=getCategoryNameById, message=message)

@app.route("/remove")
def remove():
    product_id = request.args.get("product_id")
    order_id = request.args.get("order_id")
    # Remove the specific item from the items array
    query = {
        "_id": ObjectId(order_id),
        "status": "cart",
        "items.product_id": ObjectId(product_id),
    }
    update_operation = {"$pull": {"items": {"product_id": ObjectId(product_id)}}}
    order_data.update_one(query, update_operation)
    query = {"_id": ObjectId(order_id), "items": {"$exists": True, "$size": 0}}
    # Execute the query
    empty_items_order = order_data.find_one(query)
    if empty_items_order is not None:
        order_data.delete_one({"_id": ObjectId(order_id)})
        return redirect("/customer-home?message=Plate is empty, Shop to add to cart")
    return redirect("/view-plate")

@app.route('/view-product')
def view_product():
    message = request.args.get('message')
    product_id = request.args.get('product_id')
    product = product_data.find_one({'_id': ObjectId(product_id)})
    return render_template('product-view.html', product = product, getCategoryNameById=getCategoryNameById, message=message, get_toppings_from_item=get_toppings_from_item)

# @app.route('/view-plate')
# def view_plate():
#     return render_template('view-plate.html')

@app.route("/view-plate")
def cart():
    message = request.args.get('message')
    if "role" not in session:
        return render_template(
            "login.html",
            message="Login to your Account",
        )
    if session["role"] == "Customer":
        order = order_data.find_one(
            {"customer_id": ObjectId(session["customer_id"]), "status": "cart"}
        )
        count = order_data.count_documents(
            {"customer_id": ObjectId(session["customer_id"]), "status": "cart"}
        )

        delivery_type = 'delivery'
        if count > 0:
            delivery_type = order['delivery_type']
            subtotal = 0
            total = 0
            total_quantity_items = 0
            query = {
                "customer_id": ObjectId(session["customer_id"]),
                "status": "cart",
                "items": {"$exists": True, "$size": 0},
            }
            # Execute the query
            empty_items_order = order_data.find_one(query)
            if empty_items_order is None:
                products_in_cart = order.get("items", [])
                for product_in_cart in products_in_cart:
                    product = get_product_by_product_id(product_in_cart["product_id"])
                    price = product["price"]
                    subtotal += float(price) * int(product_in_cart["quantity"])
                    total_quantity_items = total_quantity_items + int(product_in_cart["quantity"])
                    total = subtotal * 1.03
                    
                    delivery_fee = 2.99
                    if delivery_type and delivery_type == 'delivery':
                        total = total + delivery_fee
                return render_template(
                    "view-plate.html",
                    order=order,
                    products_in_cart=products_in_cart,
                    get_product_by_product_id=get_product_by_product_id,
                    total="{:.2f}".format(total * 1.08),
                    subtotal=subtotal,
                    delivery_type = delivery_type,
                    tax="{:.2f}".format(subtotal * 0.03),
                    delivery_fee = delivery_fee,
                    message=message
                )
        return redirect("/customer-home?message=No items in cart")



@app.route('/add-category')
def add_category():
    action = request.args.get('action')
    cat_id = request.args.get('cat_id')
    categories = product_category_data.find({})
    message = request.args.get('message')
    
    if action and cat_id:
        if action == 'edit':
            category = product_category_data.find_one({'_id': ObjectId(cat_id) })
            return render_template('admin-add-category.html', category=category,action=action, categories=categories, message= message)
    return render_template('admin-add-category.html', categories = categories, message=message)

# @app.route('/add-topping')
# def add_topping():
#     toppings = topping_data.find({})
#     return render_template('admin-add-topping.html', toppings = toppings)


@app.route('/add-item')
def add_item():
    products = product_data.find({})
    message = request.args.get('message')
    categories = product_category_data.find({})
    return render_template('admin-add-product.html', products = products, categories=list(categories), getCategoryNameById=getCategoryNameById, message=message)

@app.route("/delivery-orders")
def delivery_orders():
    message = request.args.get('message')
    filterType = request.args.get("status")
    print(filterType)
    print({"delivery_assigned": ObjectId(session["delivery_id"])})
    orders = order_data.find(
        {"delivery_id": ObjectId(session["delivery_id"])}
    )
    if filterType:
        query = {
            "delivery_id": ObjectId(session["delivery_id"]),
            "status": filterType,
        }
        orders = order_data.find(
           query
        )
    return render_template(
        "delivery-orders.html",
        orders=orders,
        status = filterType,
        getUpperIdFromOrderId=getUpperIdFromOrderId,
        message=message
    )

@app.route('/change-delivery-status')
def delivery_order():
    order_id = request.args.get('order_id')
    status = request.args.get('status')
    delivery_id = ObjectId(session['delivery_id'])
    if status == 'out for delivery':
        order_data.update_one({'_id': ObjectId(order_id), 'delivery_id': delivery_id}, {'$set': {'status': 'out for delivery'}})
    if status == 'delivered':
        order_data.update_one({'_id': ObjectId(order_id), 'delivery_id': delivery_id}, {'$set': {'status': 'delivered'}})
    return redirect('/delivery-orders?status='+status)

@app.route('/remove-product')
def admin_remove_product():
    
    product_id = request.args.get('product_id')
    product_data.delete_one({'_id': ObjectId(product_id)})
    return redirect('/add-item?message=item removed successfully')


@app.route('/add-delivery')
def add_delivery():
    message = request.args.get('message')
    delivery_guys = delivery_data.find({})
    return render_template('admin-add-delivery.html', delivery_guys=delivery_guys, message=message)

# Not perfect
@app.route('/admin-view-orders')
def admin_view_orders():
    message = request.args.get('message')
    orders = order_data.find({"status": {"$ne": "cart"}})
    delivery_agents = delivery_data.find()

    return render_template('admin-view-orders.html', orders=orders, getUpperIdFromOrderId=getUpperIdFromOrderId, delivery_agents=delivery_agents, message=message, get_product_by_product_id=get_product_by_product_id)


@app.route("/admin-order")
def admin_order():
    order_id = request.args.get("order_id")
    action = request.args.get("action")
    order = order_data.find_one({'_id': ObjectId(order_id)})
    if order['delivery_type'] == 'delivery':
        if action == 'accepted':
            order_data.update_one({'_id':ObjectId(order_id)}, {'$set': {'status': 'accepted'}})
        elif action == 'rejected':
            order_data.update_one({'_id': ObjectId(order_id)}, {'$set': {'status': 'rejected', 'refund_status': 'processing'}})
        elif action == 'prepared':
            order_data.update_one({'_id':ObjectId(order_id)}, {'$set': {'status': 'prepared'}})
        elif action == 'assigned':
            delivery_id = request.args.get('delivery_id')
            order_data.update_one({'_id':ObjectId(order_id)}, {'$set': {'status': 'assigned', 'delivery_id': ObjectId(delivery_id)}})
        elif action == 'process_refund':
            order_data.update_one({'_id':ObjectId(order_id)}, {'$set': {'status': 'refund processed'}})
    if order['delivery_type'] == 'pickup':
        if action == 'accepted':
            order_data.update_one({'_id':ObjectId(order_id)}, {'$set': {'status': 'accepted'}})
        elif action == 'rejected':
            order_data.update_one({'_id': ObjectId(order_id)}, {'$set': {'status': 'rejected', 'refund_status': 'processing'}})
        elif action == 'prepared':
            order_data.update_one({'_id':ObjectId(order_id)}, {'$set': {'status': 'prepared'}})
        elif action == 'picked':
            order_data.update_one({'_id':ObjectId(order_id)}, {'$set': {'status': 'Picked Up'}})
        elif action == 'process_refund':
            order_data.update_one({'_id':ObjectId(order_id)}, {'$set': {'status': 'refund processed'}})
    return redirect('/admin-view-orders')

@app.route('/payment-portal')
def payment_portal():
    message = request.args.get('message')
    subtotal = request.args.get('subtotal')
    order_id = request.args.get('order_id')
    total = request.args.get('total')
    delivery_type = request.args.get('delivery_type')
    return render_template('customer-payment.html', total = total, order_id = order_id, subtotal=subtotal, message=message, delivery_type=delivery_type)

@app.route('/verify-transaction', methods=['POST'])
def verify_payment():
    order_id = request.form.get("order_id")
    amount = request.form.get("total")
    customer_id = ObjectId(session["customer_id"])
    name = request.form.get("card_name")
    number = request.form.get("card_number")
    payment_type = request.form.get("payment_type")
    expiry = request.form.get("expiry")
    cvv = request.form.get("cvv")
    street = request.form.get("street")
    zip = request.form.get("zip")
    city = request.form.get("city")
    # address = request.form.get('address')
    # subtotal = request.form.get('subtotal')
    order_details = {}
    payment_details = {
            "order_id": ObjectId(order_id),
            "amount": amount,
            "customer_id": customer_id,
            "card_holder": name,
            "card_id": number,
            "payment_type": payment_type,
            "expiry_date": expiry, 
            "cvv": cvv,
            "payment_date": datetime.datetime.now().strftime("%m-%d-%Y")
        }
    payment_collection.insert_one(payment_details)

    order_details = {
            "status": "pending",
            "amount": amount,
            "street":street,
            "zip":zip,
            "city":city,
            'order_date': datetime.datetime.now().strftime("%m-%d-%Y")
        }
    order_data.update_one(
        {"_id": ObjectId(order_id)},
        {
            "$set": order_details
        },
    )
    return redirect("/customer-orders?message=order placed successful")


@app.route('/customer-orders')
def customer_orders():
    message = request.args.get("message")
    if "role" not in session:
        return render_template(
            "login.html",
            message="No Orders So Far",
        )
    if session["role"] == "Customer":
        orders = order_data.find(
            {"customer_id": ObjectId(session["customer_id"]), "status": {"$ne": "cart"}}
        )
        count = order_data.count_documents(
            {"customer_id": ObjectId(session["customer_id"]), "status": {"$ne": "cart"}}
        )
        print( 'customer-orders')
        return render_template(
                "customer-orders.html",
                orders=orders,
                orders_count = count,
                get_product_by_product_id=get_product_by_product_id,
                getUpperIdFromOrderId=getUpperIdFromOrderId,
                message=request.args.get("message")
            )
    return render_template("customer-orders.html", message=message)

#perfect
def getUpperIdFromOrderId(order_id):
    stri = str(order_id)
    substr = stri[-6: -2].upper()
    return substr

# Perfect
@app.route('/add-menu-item', methods=['post'])
def add_menu_item():
    category_id = request.form.get("category_id")
    price = request.form.get("price")
    name = request.form.get("name")
    picture = request.files.get("picture")
    path = APP_ROOT + "/static/images/" + picture.filename
    description = request.form.get("description")
    toppings = request.form.getlist('topping_name[]')
    optional = []
    for topping in zip(toppings):
        optional.append(topping)
    picture.save(path)
    query = {"name": name}
    count = product_data.count_documents(query)
    if count == 0:
        query = {
            "name": name,
            "picture": picture.filename,
            "price": price,
            "category_id": ObjectId(category_id),
            "description": description,
            "optional_topping": optional
        }
        product_data.insert_one(query)
        return redirect("/add-item?message= "+name+ " added to menu")
    else:
        return redirect("/add-item?message= duplicate item cannot be added to menu")


def get_toppings_from_item(item_id):
    items = product_data.find_one({'_id': ObjectId(item_id)})
    return items['optional_topping']
    
# Perfect
@app.route('/admin-add-category', methods = ['POST'])
def admin_add_category():
    cat_id = request.form.get('cat_id')
    category = request.form.get("category_name")
    if cat_id:
        product_category_data.update_one({'_id': ObjectId(cat_id)}, {'$set': {'category_name': category}})
        return redirect('/add-category?message=Updated successfully')
    if product_category_data.count_documents({'category_name': category}) == 0:
        product_category_data.insert_one({'category_name': category})
        return redirect('/add-category?message=Added successfully')
    return redirect('/add-category?message=duplicate category')


# Perfect
@app.route('/admin-add-delivery', methods=['POST'])
def admin_add_delivery():
    name = request.form.get('name')
    phone = request.form.get('phone')
    email = request.form.get('email')
    password = request.form.get('password')
    count = delivery_data.count_documents({'email': email})
    if count == 0:
        delivery_data.insert_one({'email': email, 'name':name, 'phone':phone, 'password':password})
        return redirect('/add-delivery?message=agent added successfully!')
    return redirect('/add-delivery?message=username already exists!')


@app.route("/login-verify", methods=["post"])
def login_verify():
    message = request.args.get('message')
    role = request.form.get("role")
    username = request.form.get("email")
    password = request.form.get("password")
    if role == "Admin":
        query = {"email": username, "password": password}
        if admin_data.count_documents({}) == 0:
            admin_data.insert_one(
                {"email": "admin@gmail.com", "password": "admin"}
            )
        admin = admin_data.find_one(query)
        print(admin_data.count_documents(query))
        if admin is not None:
            session["admin_id"] = str(admin["_id"])
            session["role"] = "Admin"
            session["login_count"] = 1
            return redirect("/admin-home")
        return render_template(
            "admin-login.html",
            username=username,
            message="Invalid username or password, please try again!",
        )
    elif role == "Delivery":
        query = {"email": username, "password": password}
        delivery = delivery_data.find_one(query)
        if delivery is not None:
            session["role"] = "Delivery"
            session["delivery_id"] = str(delivery["_id"])
            session["login_count"] = 1
            return redirect("/delivery-home")
        return render_template(
            "delivery-login.html",
            username=username,
            message="Invalid username or password, please try again!",
        )
    elif role == "Customer":
        query = {"email": username, "password": password}
        customer = customer_data.find_one(query)
        if customer is not None:
            session["role"] = "Customer"
            session["customer_id"] = str(customer["_id"])
            session["login_count"] = 1
            return redirect("/customer-home")
        return render_template(
            "login.html",
            username=username,
            message="Invalid username or password, please try again!",
        )
    elif role == "NewCustomer":
        first_name = request.form.get("first_name")
        last_name = request.form.get("last_name")
        email = request.form.get("email")
        phone = request.form.get("phone")
        street = request.form.get("street")
        zip = request.form.get("zip")
        street = request.form.get("city")
        dob = request.form.get("dob")
        gender = request.form.get("gender")
        password = request.form.get('password')
        countEmail = customer_data.count_documents({"email": email})
        countPhone = customer_data.count_documents({"phone": phone})
        print(countEmail, countPhone)
        if countEmail == 0 and countPhone == 0:
            customer_data.insert_one(
                {
                    "first_name": first_name,
                    "last_name": last_name,
                    "phone": phone,
                    "email": email,
                    "phone": phone,
                    "password": password,
                    "street": street,
                    "zip":zip,
                    "dob":dob,
                    "gender":gender
                }
            )
            return render_template(
                "login.html",
                username=email,
                message="account created successfully! you can login now!",
            )
        return render_template(
            "sign-up.html",
            message="User already exist with given email or phone! Try with different one",
            name=name,
            phone=phone,
            email=email,
            address=address,
        )
    return render_template("login.html")

#perfect
def getCategoryNameById(category_id):
    category = product_category_data.find_one({'_id': ObjectId(category_id)})
    return category['category_name']

# Not perfect
def is_product_in_cart(product_id):
    if 'role' not in session:
        return False
    customer_id = session['customer_id']
    query_to_cart_status = {'status':'cart', 'customer_id': ObjectId(customer_id)}
    count_status_cart = order_data.count_documents(query_to_cart_status)
    if count_status_cart > 0:
        order = order_data.find_one(query_to_cart_status)
        order_id = order['_id']
        count_in_cart = order_data.count_documents(
                {
                    "_id": ObjectId(order_id),
                    "status": "cart",
                    "items.product_id": ObjectId(product_id),
                }
            )
        if count_in_cart > 0:
            return True
    return False


def get_product_by_product_id(product_id):
    query = {"_id": product_id}
    product = product_data.find_one(query)
    return product

if __name__ == '__main__':
    app.run(debug=True, port='5001')
