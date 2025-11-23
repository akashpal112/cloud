# app.py - Akshu Cloud Gallery Backend (Multi-User Secured with Private Contacts)

from flask import Flask, request, jsonify, session, send_from_directory
from flask_bcrypt import Bcrypt
from flask_session import Session
from datetime import datetime
from functools import wraps 
import os
from dotenv import load_dotenv

# Database and Cloudinary Imports
from pymongo import MongoClient
from bson.objectid import ObjectId
import cloudinary
import cloudinary.uploader

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

# Database connection
try:
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    users_collection = db['users']
    photos_collection = db['photos']
    # NEW: Contacts Collection
    contacts_collection = db['contacts'] 
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
        return jsonify({"success": True, "message": "Login successful.", "username": user['username']})
    else:
        return jsonify({"success": False, "message": "Invalid username or password."})

@app.route('/api/logout', methods=['POST'])
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    return jsonify({"success": True, "message": "Logged out successfully."})


# --- 3. PHOTO MANAGEMENT ---

@app.route('/api/upload', methods=['POST'])
@login_required
def upload_photo():
    if 'file' not in request.files:
        return jsonify({"success": False, "message": "No file part."}), 400
    
    file_to_upload = request.files['file']
    
    if file_to_upload.filename == '':
        return jsonify({"success": False, "message": "No selected file."}), 400

    try:
        upload_result = cloudinary.uploader.upload(file_to_upload, folder=session['username'])
        
        photo_data = {
            "user_id": session['user_id'],
            "url": upload_result['secure_url'],
            "public_id": upload_result['public_id'],
            "filename": file_to_upload.filename,
            "uploaded_at": datetime.now()
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
        photos_list.append({
            "_id": str(photo.get('_id')),
            "url": photo.get('url'),
            "public_id": photo.get('public_id')
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


# ----------------------------------------------------------------------
# --- 4. NEW API ENDPOINTS: PRIVATE CONTACTS ---
# ----------------------------------------------------------------------

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
        "user_id": session.get('user_id'), # Link contact to the current logged-in user
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

@app.route('/api/contacts', methods=['GET'])
@login_required
def get_contacts():
    current_user_id = session.get('user_id')
    
    try:
        # Crucial security check: fetch only contacts belonging to the current user
        user_contacts = contacts_collection.find({"user_id": current_user_id}).sort("name", 1) 
        
        contacts_list = []
        for contact in user_contacts:
            contacts_list.append({
                "_id": str(contact.get('_id')),
                "name": contact.get('name'),
                "phone": contact.get('phone'),
                "email": contact.get('email', 'N/A'),
                "created_at": contact.get('created_at').strftime("%Y-%m-%d %H:%M:%S")
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
        # Ensure the contact belongs to the user before deleting
        result = contacts_collection.delete_one({"_id": ObjectId(contact_id), "user_id": current_user_id})
        
        if result.deleted_count == 1:
            return jsonify({"success": True, "message": "Contact deleted successfully."})
        else:
            return jsonify({"success": False, "message": "Contact not found or unauthorized."}), 404
    
    except Exception as e:
        print(f"❌ Error deleting contact {contact_id}: {e}")
        return jsonify({"success": False, "message": "Failed to delete contact."}), 500

# --- 5. STATIC FILE ROUTES ---

@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/<path:filename>')
def serve_static(filename):
    if filename in ['app.py', '.env']:
        return "Access Denied", 403
    return send_from_directory(app.static_folder, filename)

if __name__ == '__main__':
    print("-------------------------------------------------------")
    print("  Akshu Cloud Gallery Backend Server Starting...")
    print("-------------------------------------------------------")
    app.run(host='0.0.0.0', port=5000)