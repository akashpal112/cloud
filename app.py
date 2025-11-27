# app.py - Akshu Cloud Gallery Backend (Fully Merged and Updated with Game Logic & Razorpay)

from flask import Flask, request, jsonify, session, send_from_directory
from flask_bcrypt import Bcrypt
from flask_session import Session
from datetime import datetime, timedelta 
from functools import wraps 
import os
from dotenv import load_dotenv
import random 
import razorpay # NEW: For payment gateway integration

# Database and Cloudinary Imports
from pymongo import MongoClient
from bson.objectid import ObjectId
import cloudinary
import cloudinary.uploader
import vobject 

# Load environment variables from .env file
load_dotenv()

# --- 1. CONFIGURATION & INITIALIZATION ---
app = Flask(__name__, static_folder='.')
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", "fallback_secret_key")
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = False
Session(app)
bcrypt = Bcrypt(app)

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("DB_NAME")

# Razorpay Configuration (Must be set in .env)
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")
# Initialize Razorpay Client
try:
    razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
    print("✅ Razorpay Client initialized.")
except Exception as e:
    print(f"⚠️ Razorpay Initialization Warning (Check keys): {e}")


# Database connection
try:
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    users_collection = db['users']
    photos_collection = db['photos']
    contacts_collection = db['contacts'] 
    
    # NEW: Game Collections
    wallets_collection = db['wallets']
    predictions_collection = db['predictions']
    game_rounds_collection = db['game_rounds'] 
    
    print("✅ MongoDB connection successful.")
except Exception as e:
    print(f"❌ MongoDB connection error: {e}")

# Cloudinary configuration
CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET")

cloudinary.config( 
    cloud_name = CLOUDINARY_CLOUD_NAME, 
    api_key = CLOUDINARY_API_KEY, 
    api_secret = CLOUDINARY_API_SECRET,
    secure = True
)
print("✅ Cloudinary configuration loaded.")


# --- 2. AUTHENTICATION & UTILITIES ---

def login_required(f):
    """Decorator to protect API routes, ensuring user is logged in."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({"success": False, "message": "Unauthorized access. Please log in."}), 401
        return f(*args, **kwargs)
    return decorated_function

# --- NEW UTILITY FUNCTION: Initialize Wallet ---
def initialize_wallet(user_id, initial_balance=1000):
    """Checks if a user has a wallet. If not, creates one with an initial bonus."""
    if wallets_collection.find_one({"user_id": user_id}) is None:
        wallets_collection.insert_one({
            "user_id": user_id,
            "balance": initial_balance, # 1000 Free Akshu Tokens as bonus
            "last_updated": datetime.now()
        })
        print(f"💰 Wallet created for user {user_id} with {initial_balance} tokens.")

@app.route('/api/status', methods=['GET'])
def get_status():
    is_logged_in = 'user_id' in session
    username = session.get('username', 'Guest')
    return jsonify({"isLoggedIn": is_logged_in, "username": username})

@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if users_collection.find_one({"username": username}):
        return jsonify({"success": False, "message": "Username already exists."})
    
    hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
    users_collection.insert_one({'username': username, 'password': hashed_password})
    
    return jsonify({"success": True, "message": "Registration successful! You can now log in."})

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    user = users_collection.find_one({"username": username})
    
    if user and bcrypt.check_password_hash(user['password'], password):
        session['user_id'] = str(user['_id'])
        session['username'] = user['username']
        
        initialize_wallet(session['user_id']) 
        
        return jsonify({"success": True, "message": "Login successful.", "username": user['username']})
    else:
        return jsonify({"success": False, "message": "Invalid username or password."})

@app.route('/api/logout', methods=['POST'])
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    return jsonify({"success": True, "message": "Logged out successfully."})


# --- 3. PHOTO MANAGEMENT (CRUD) ---

@app.route('/api/upload', methods=['POST'])
@login_required
def upload_photo():
    if 'file' not in request.files:
        return jsonify({"success": False, "message": "No file part."}), 400
    
    file_to_upload = request.files['file']
    
    if file_to_upload.filename == '':
        return jsonify({"success": False, "message": "No selected file."}), 400

    location_data = request.form.get('location', '')
    
    try:
        upload_result = cloudinary.uploader.upload(file_to_upload, folder=session['username'])
        
        photo_data = {
            "user_id": session['user_id'],
            "url": upload_result['secure_url'],
            "public_id": upload_result['public_id'],
            "filename": file_to_upload.filename,
            "uploaded_at": datetime.now(),
            "location": location_data
        }
        photos_collection.insert_one(photo_data)
        
        return jsonify({"success": True, "message": "File uploaded successfully.", "url": upload_result['secure_url']})

    except Exception as e:
        print(f"❌ Upload Error: {e}")
        return jsonify({"success": False, "message": f"Upload failed: {str(e)}"}), 500

@app.route('/api/photos', methods=['GET'])
@login_required
def get_photos():
    current_user_id = session['user_id']
    user_photos = photos_collection.find({"user_id": current_user_id}).sort("uploaded_at", -1)
    
    photos_list = []
    for photo in user_photos:
        uploaded_at_str = photo.get('uploaded_at').strftime("%Y-%m-%d %H:%M:%S") if photo.get('uploaded_at') else 'N/A'
        
        photos_list.append({
            "_id": str(photo.get('_id')),
            "url": photo.get('url'),
            "public_id": photo.get('public_id'),
            "uploaded_at": uploaded_at_str, 
            "location": photo.get('location', 'N/A')
        })
        
    return jsonify({"success": True, "photos": photos_list})

@app.route('/api/photos/<photo_id>', methods=['DELETE'])
@login_required
def delete_photo(photo_id):
    current_user_id = session['user_id']
    
    try:
        photo_doc = photos_collection.find_one({"_id": ObjectId(photo_id), "user_id": current_user_id})
        
        if not photo_doc:
            return jsonify({"success": False, "message": "Photo not found or unauthorized."}), 404
        
        public_id = photo_doc['public_id']
        
        cloudinary.uploader.destroy(public_id)
        photos_collection.delete_one({"_id": ObjectId(photo_id)})
        
        return jsonify({"success": True, "message": "Photo deleted successfully."})

    except Exception as e:
        print(f"❌ Delete Error: {e}")
        return jsonify({"success": False, "message": f"Deletion failed: {str(e)}"}), 500


# --- 4. PRIVATE CONTACTS MANAGEMENT (CRUD) ---

@app.route('/api/contacts', methods=['POST'])
@login_required
def add_contact():
    data = request.get_json()
    name = data.get('name')
    phone = data.get('phone')
    email = data.get('email', '')
    
    if not name or not phone:
        return jsonify({"success": False, "message": "Name and Phone are required."}), 400

    contact_data = {
        "user_id": session.get('user_id'),
        "name": name,
        "phone": phone,
        "email": email,
        "created_at": datetime.now()
    }

    try:
        result = contacts_collection.insert_one(contact_data)
        return jsonify({"success": True, "message": "Contact added successfully.", "contact_id": str(result.inserted_id)})
    except Exception as e:
        print(f"❌ Error adding contact: {e}")
        return jsonify({"success": False, "message": "Failed to save contact."}), 500
        
@app.route('/api/import_vcf', methods=['POST'])
@login_required
def import_vcf():
    current_user_id = session.get('user_id')
    
    if 'vcf_file' not in request.files:
        return jsonify({"success": False, "message": "No file part in the request."}), 400

    vcf_file = request.files['vcf_file']
    
    if vcf_file.filename == '':
        return jsonify({"success": False, "message": "No selected file."}), 400
        
    if not vcf_file.filename.endswith('.vcf'):
        return jsonify({"success": False, "message": "Invalid file type. Please upload a .vcf file."}), 400
    
    try:
        vcf_content = vcf_file.read().decode('utf-8') 
    except Exception as e:
        return jsonify({"success": False, "message": f"Could not read file content: {e}"}), 400

    contacts_imported = 0

    try:
        for vcard in vobject.readComponents(vcf_content): 
            name = ""
            phone = ""
            email = ""

            if hasattr(vcard, 'fn'):
                name = str(vcard.fn.value)
            elif hasattr(vcard, 'n'):
                n_parts = vcard.n.value
                name = f"{n_parts.given} {n_parts.family}" if n_parts.given or n_parts.family else "Unknown Name"
            
            if not name:
                name = "Unknown Contact (VCF Import)"

            if hasattr(vcard, 'tel_list'):
                for tel in vcard.tel_list:
                    phone = tel.value
                    if 'CELL' in tel.params.get('TYPE', []) or 'VOICE' in tel.params.get('TYPE', []):
                        break 
            
            if hasattr(vcard, 'email_list') and vcard.email_list:
                email = vcard.email_list[0].value
                
            
            if phone:
                contacts_collection.insert_one({
                    "user_id": current_user_id,
                    "name": name,
                    "phone": phone,
                    "email": email,
                    "source": "vcf_import",
                    "created_at": datetime.utcnow()
                })
                contacts_imported += 1
            
        if contacts_imported > 0:
            return jsonify({
                "success": True, 
                "message": f"Successfully imported {contacts_imported} contact(s)."
            }), 200
        else:
            return jsonify({
                "success": False, 
                "message": "No valid contacts found in the VCF file (0 phone numbers extracted)."
            }), 400

    except Exception as e:
        print(f"❌ Error during VCF parsing: {e}")
        return jsonify({
            "success": False, 
            "message": f"VCF parsing failed. Please check file format. Error: {e}"
        }), 500


@app.route('/api/contacts', methods=['GET'])
@login_required
def get_contacts():
    current_user_id = session.get('user_id')
    
    try:
        user_contacts = contacts_collection.find({"user_id": current_user_id}).sort("name", 1) 
        
        contacts_list = []
        for contact in user_contacts:
            contacts_list.append({
                "_id": str(contact.get('_id')),
                "name": contact.get('name'),
                "phone": contact.get('phone'),
                "email": contact.get('email', 'N/A'),
                "created_at": contact.get('created_at').strftime("%Y-%m-%d %H:%M:%S") if contact.get('created_at') else 'N/A'
            })
            
        return jsonify({"success": True, "contacts": contacts_list})
    
    except Exception as e:
        print(f"❌ Error fetching contacts: {e}")
        return jsonify({"success": False, "message": "Failed to retrieve contacts."}), 500

@app.route('/api/contacts/<contact_id>', methods=['DELETE'])
@login_required
def delete_contact(contact_id):
    current_user_id = session.get('user_id')
    
    try:
        result = contacts_collection.delete_one({"_id": ObjectId(contact_id), "user_id": current_user_id})
        
        if result.deleted_count == 1:
            return jsonify({"success": True, "message": "Contact deleted successfully."})
        else:
            return jsonify({"success": False, "message": "Contact not found or unauthorized."}), 404
    
    except Exception as e:
        print(f"❌ Error deleting contact {contact_id}: {e}")
        return jsonify({"success": False, "message": "Failed to delete contact."}), 500

# ----------------------------------------------------------------------
# --- 5. WALLET & BALANCE API ---
# ----------------------------------------------------------------------

@app.route('/api/wallet/balance', methods=['GET'])
@login_required
def get_wallet_balance():
    current_user_id = session['user_id']
    
    wallet = wallets_collection.find_one({"user_id": current_user_id})
    
    if not wallet:
        initialize_wallet(current_user_id) 
        wallet = wallets_collection.find_one({"user_id": current_user_id})

    return jsonify({
        "success": True, 
        "balance": wallet.get('balance', 0)
    })

# ----------------------------------------------------------------------
# --- 6. GAME RESULT LOGIC ---
# ----------------------------------------------------------------------

def generate_game_result():
    """Generates the result of the next color prediction round."""
    choices = ['red', 'green', 'violet']
    # Probabilities: Red (45%), Green (45%), Violet (10%)
    weights = [45, 45, 10]
    
    winning_color = random.choices(choices, weights=weights, k=1)[0]
    
    last_round = game_rounds_collection.find_one(sort=[('round_id', -1)])
    next_round_id = (last_round['round_id'] + 1) if last_round else 1
    
    round_doc = {
        "round_id": next_round_id,
        "winning_color": winning_color,
        "is_processed": False,
        "result_time": datetime.now()
    }
    game_rounds_collection.insert_one(round_doc)
    print(f"🎲 Round {next_round_id} result: {winning_color} recorded.")
    return round_doc

def process_round_winnings(round_id, winning_color):
    """Processes all pending bets for the given round and distributes winnings."""
    
    pending_bets = predictions_collection.find({"status": "pending"}).limit(100) 

    total_winnings_distributed = 0
    
    for bet in pending_bets:
        user_id = bet['user_id']
        amount = bet['amount']
        prediction = bet['prediction']
        payout = 0
        
        # Calculate Payout
        if prediction == winning_color:
            if winning_color == 'red' or winning_color == 'green':
                payout = amount * 2  # 2X win (Bet amount + Win amount)
            elif winning_color == 'violet':
                payout = amount * 5  # 5X win
        
        if payout > 0:
            # Credit the wallet
            wallets_collection.update_one(
                {"user_id": user_id},
                {"$inc": {"balance": payout}}
            )
            
            # Update prediction status
            predictions_collection.update_one(
                {"_id": bet['_id']},
                {"$set": {"status": "won", "winnings": payout, "processed_round": round_id}}
            )
            total_winnings_distributed += payout
            
        else:
            # Update prediction status (Lost)
            predictions_collection.update_one(
                {"_id": bet['_id']},
                {"$set": {"status": "lost", "processed_round": round_id}}
            )
            
    # Set the round as processed
    game_rounds_collection.update_one(
        {"round_id": round_id},
        {"$set": {"is_processed": True, "total_payout": total_winnings_distributed}}
    )
    
    print(f"💰 Round {round_id} processed. Winnings: {total_winnings_distributed} tokens.")


@app.route('/api/game/run_round', methods=['POST'])
@login_required 
def run_game_round():
    """A testing route to manually trigger result generation and processing."""
    
    # 1. Generate the next result
    round_result = generate_game_result()
    round_id = round_result['round_id']
    winning_color = round_result['winning_color']
    
    # 2. Process the winnings for this new round
    process_round_winnings(round_id, winning_color)
    
    return jsonify({
        "success": True,
        "message": f"Game Round {round_id} completed.",
        "winning_color": winning_color
    })


# ----------------------------------------------------------------------
# --- 7. COLOR PREDICTION GAME API ---
# ----------------------------------------------------------------------

@app.route('/api/game/predict', methods=['POST'])
@login_required
def place_prediction_bet():
    data = request.get_json()
    user_id = session['user_id']
    prediction = data.get('prediction') # e.g., 'red', 'green', 'violet'
    amount = data.get('amount')
    
    if not prediction or not amount or amount <= 0:
        return jsonify({"success": False, "message": "Invalid prediction or amount."}), 400

    wallet = wallets_collection.find_one({"user_id": user_id})
    if wallet['balance'] < amount:
        return jsonify({"success": False, "message": "Insufficient Akshu Tokens."}), 402

    try:
        # 1. Deduct Bet Amount (Transaction)
        new_balance = wallet['balance'] - amount
        wallets_collection.update_one(
            {"user_id": user_id},
            {"$set": {"balance": new_balance, "last_updated": datetime.now()}}
        )

        # 2. Record the Prediction/Bet
        prediction_doc = {
            "user_id": user_id,
            "prediction": prediction,
            "amount": amount,
            "status": "pending",
            "placed_at": datetime.now()
        }
        predictions_collection.insert_one(prediction_doc)

        return jsonify({
            "success": True, 
            "message": f"Bet of {amount} tokens on {prediction} placed successfully.",
            "new_balance": new_balance
        })

    except Exception as e:
        print(f"❌ Prediction Error: {e}")
        return jsonify({"success": False, "message": "Failed to place bet due to server error."}), 500


# ----------------------------------------------------------------------
# --- 8. GAME STATUS API ---
# ----------------------------------------------------------------------

@app.route('/api/game/status', methods=['GET'])
@login_required
def get_game_status():
    """Fetches current round info, timer, and last results."""
    
    round_duration = 60 # 60 seconds per round cycle (can be adjusted)
    
    latest_round = game_rounds_collection.find_one(sort=[('round_id', -1)])
    
    if latest_round:
        time_since_last_result = (datetime.now() - latest_round['result_time']).total_seconds()
        time_remaining = max(0, int(round_duration - time_since_last_result))
        current_round_id = latest_round['round_id'] + 1
    else:
        time_remaining = round_duration
        current_round_id = 1


    # 2. Get the last 10 processed results
    past_results = game_rounds_collection.find({"is_processed": True}).sort('round_id', -1).limit(10)
    results_list = [
        {"round_id": r['round_id'], "color": r['winning_color']}
        for r in past_results
    ]
    
    return jsonify({
        "success": True,
        "current_round_id": current_round_id, 
        "time_remaining": time_remaining,
        "past_results": results_list
    })


# ----------------------------------------------------------------------
# --- 9. RAZORPAY PAYMENT API: Create Order and Verify ---
# ----------------------------------------------------------------------

@app.route('/api/payment/create_order', methods=['POST'])
@login_required
def create_payment_order():
    """Creates a Razorpay order for purchasing Akshu Tokens."""
    
    data = request.get_json()
    amount_in_tokens = data.get('amount_tokens')
    
    if not amount_in_tokens or amount_in_tokens < 100:
        return jsonify({"success": False, "message": "Minimum purchase is 100 tokens."}), 400
    
    # 1 Token = 1 INR (Amount in paise for Razorpay)
    amount_in_paise = amount_in_tokens * 100
    
    order_data = {
        'amount': amount_in_paise,
        'currency': 'INR',
        'receipt': f"receipt_{session['user_id']}_{datetime.now().timestamp()}",
        'payment_capture': '1',
        'notes': {
            'user_id': session['user_id'],
            'tokens': amount_in_tokens
        }
    }

    try:
        order = razorpay_client.order.create(data=order_data)
        return jsonify({
            "success": True,
            "order_id": order['id'],
            "amount": order['amount'],
            "currency": order['currency'],
            "key_id": RAZORPAY_KEY_ID 
        })
    except Exception as e:
        print(f"❌ Razorpay Order Creation Error: {e}")
        return jsonify({"success": False, "message": "Failed to create payment order."}), 500

@app.route('/api/payment/verify', methods=['POST'])
@login_required
def verify_payment():
    """Verifies the payment signature and credits the user's wallet with tokens."""
    
    data = request.get_json()
    razorpay_payment_id = data.get('razorpay_payment_id')
    razorpay_order_id = data.get('razorpay_order_id')
    razorpay_signature = data.get('razorpay_signature')
    
    try:
        # Verify the signature
        razorpay_client.utility.verify_payment_signature({
            'razorpay_order_id': razorpay_order_id,
            'razorpay_payment_id': razorpay_payment_id,
            'razorpay_signature': razorpay_signature
        })
        
        # Fetch the order details to get the token amount
        order = razorpay_client.order.fetch(razorpay_order_id)
        tokens_to_credit = order['notes']['tokens'] 
        
        # CRUCIAL: Credit the user's wallet
        wallets_collection.update_one(
            {"user_id": session['user_id']},
            {"$inc": {"balance": int(tokens_to_credit)},
             "$set": {"last_updated": datetime.now()}}
        )
        
        return jsonify({
            "success": True, 
            "message": f"Payment successful. {tokens_to_credit} tokens credited.",
            "tokens_credited": tokens_to_credit
        })
        
    except Exception as e:
        print(f"❌ Razorpay Verification Failed: {e}")
        return jsonify({"success": False, "message": "Payment verification failed or signature mismatch."}), 400


# ----------------------------------------------------------------------
# --- 10. STATIC FILE ROUTES (PWA & SECURITY) ---
# ----------------------------------------------------------------------

@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/<path:filename>')
def serve_static(filename):
    # Security: Prevent direct access to backend/config files
    if filename in ['app.py', '.env', 'requirements.txt']:
        return "Access Denied", 403

    if filename == 'manifest.json':
        return send_from_directory(app.static_folder, filename, mimetype='application/manifest+json')
    elif filename == 'service-worker.js':
        return send_from_directory(app.static_folder, filename, mimetype='application/javascript')
    
    return send_from_directory(app.static_folder, filename)

if __name__ == '__main__':
    print("-------------------------------------------------------")
    print("  Akshu Cloud Gallery Backend Server Starting...")
    print("-------------------------------------------------------")
    app.run(host='0.0.0.0', port=5000)