# app.py - Akshu Cloud Gallery Backend (Multi-User Secured with Private Contacts)

from flask import Flask, request, jsonify, session, send_from_directory
from flask_bcrypt import Bcrypt
from flask_session import Session
from datetime import datetime
from functools import wraps 
import os
import logging
from dotenv import load_dotenv

# Database and Cloudinary Imports
from pymongo import MongoClient
from bson.objectid import ObjectId
from werkzeug.utils import secure_filename # For robust file security
import cloudinary
import cloudinary.uploader
import vobject 

# --- Logging Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    # Check connection immediately
    client.admin.command('ping') 
    db = client[DB_NAME]
    users_collection = db['users']
    photos_collection = db['photos']
    contacts_collection = db['contacts'] 
    logging.info("✅ MongoDB connection successful.")
except Exception as e:
    logging.error(f"❌ MongoDB connection error: {e}")
    # Handle the case where the application cannot run without a database
    # In a real app, you might raise an error here. For now, we continue with a warning.

# Cloudinary configuration
CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET")

if CLOUDINARY_CLOUD_NAME and CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET:
    cloudinary.config( 
        cloud_name = CLOUDINARY_CLOUD_NAME, 
        api_key = CLOUDINARY_API_KEY, 
        api_secret = CLOUDINARY_API_SECRET,
        secure = True
    )
    logging.info("✅ Cloudinary configuration loaded.")
else:
    logging.warning("⚠️ Cloudinary credentials missing. Upload functionality will fail.")


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
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')

        if not username or not password:
             return jsonify({"success": False, "message": "Username and password are required."}), 400

        if users_collection.find_one({"username": username}):
            return jsonify({"success": False, "message": "Username already exists."})
        
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        users_collection.insert_one({'username': username, 'password': hashed_password})
        
        return jsonify({"success": True, "message": "Registration successful! You can now log in."})
    except Exception as e:
        logging.error(f"Registration failed: {e}")
        return jsonify({"success": False, "message": "A server error occurred during registration."}), 500

@app.route('/api/login', methods=['POST'])
def login():
    try:
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
    except Exception as e:
        logging.error(f"Login failed: {e}")
        return jsonify({"success": False, "message": "A server error occurred during login."}), 500

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
        
    filename = secure_filename(file_to_upload.filename) # Secure the filename

    try:
        # Using the secured filename for the public_id prefix
        public_id_prefix = os.path.splitext(filename)[0]
        
        # Upload using the username as the folder for organization
        upload_result = cloudinary.uploader.upload(
            file_to_upload, 
            folder=session['username'],
            public_id=public_id_prefix, 
            unique_filename=True, # Important to avoid overwrites
            overwrite=False
        )
        
        photo_data = {
            "user_id": session['user_id'],
            "url": upload_result['secure_url'],
            "public_id": upload_result['public_id'],
            "filename": filename,
            "uploaded_at": datetime.now()
        }
        photos_collection.insert_one(photo_data)
        
        return jsonify({"success": True, "message": "File uploaded successfully.", "url": upload_result['secure_url']})

    except Exception as e:
        logging.error(f"❌ Upload Error for file {filename}: {e}")
        return jsonify({"success": False, "message": f"Upload failed: {str(e)}"}), 500

@app.route('/api/photos', methods=['GET'])
@login_required
def get_photos():
    current_user_id = session['user_id']
    
    try:
        user_photos = photos_collection.find({"user_id": current_user_id}).sort("uploaded_at", -1)
        
        photos_list = []
        for photo in user_photos:
            photos_list.append({
                "_id": str(photo.get('_id')),
                "url": photo.get('url'),
                "public_id": photo.get('public_id')
            })
            
        return jsonify({"success": True, "photos": photos_list})
    except Exception as e:
        logging.error(f"Error fetching photos for user {current_user_id}: {e}")
        return jsonify({"success": False, "message": "Failed to retrieve photos."}), 500

@app.route('/api/photos/<photo_id>', methods=['DELETE'])
@login_required
def delete_photo(photo_id):
    current_user_id = session['user_id']
    
    try:
        # Validate ObjectId first
        if not ObjectId.is_valid(photo_id):
            return jsonify({"success": False, "message": "Invalid Photo ID format."}), 400

        photo_doc = photos_collection.find_one({"_id": ObjectId(photo_id), "user_id": current_user_id})
        
        if not photo_doc:
            return jsonify({"success": False, "message": "Photo not found or unauthorized."}), 404
        
        public_id = photo_doc['public_id']
        
        # 1. Delete from Cloudinary
        cloudinary.uploader.destroy(public_id)
        
        # 2. Delete from MongoDB
        photos_collection.delete_one({"_id": ObjectId(photo_id)})
        
        return jsonify({"success": True, "message": "Photo deleted successfully."})

    except Exception as e:
        logging.error(f"❌ Delete Error for photo {photo_id}: {e}")
        return jsonify({"success": False, "message": f"Deletion failed: {str(e)}"}), 500


# ----------------------------------------------------------------------
# --- 4. NEW API ENDPOINTS: PRIVATE CONTACTS ---
# ----------------------------------------------------------------------

@app.route('/api/contacts', methods=['POST'])
@login_required
def add_contact():
    data = request.get_json()
    # Basic data cleaning
    name = data.get('name', '').strip()
    phone = data.get('phone', '').strip()
    email = data.get('email', '').strip()
    
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
        logging.error(f"❌ Error adding contact manually: {e}")
        return jsonify({"success": False, "message": "Failed to save contact."}), 500
        
# --- VCF Contact Import Route (Improved Parsing) ---
@app.route('/api/import_vcf', methods=['POST'])
@login_required
def import_vcf():
    current_user_id = session.get('user_id')
    
    if 'vcf_file' not in request.files:
        return jsonify({"success": False, "message": "No file part in the request."}), 400

    vcf_file = request.files['vcf_file']
    
    if vcf_file.filename == '':
        return jsonify({"success": False, "message": "No selected file."}), 400
        
    filename = secure_filename(vcf_file.filename)
    if not filename.lower().endswith('.vcf'):
        return jsonify({"success": False, "message": "Invalid file type. Please upload a .vcf file."}), 400
    
    try:
        # Read the file content and decode it
        vcf_content = vcf_file.read().decode('utf-8') 
    except Exception as e:
        return jsonify({"success": False, "message": f"Could not read file content: {e}"}), 400

    contacts_imported = 0

    try:
        # Parse VCF content
        for vcard in vobject.readComponents(vcf_content): 
            name = ""
            phone = ""
            email = ""

            # 1. Get Name (Prioritize FN, then N)
            if hasattr(vcard, 'fn'):
                name = str(vcard.fn.value).strip()
            elif hasattr(vcard, 'n'):
                # Better handling of structured name parts
                n_parts = vcard.n.value
                parts = [p for p in [n_parts.given, n_parts.family, n_parts.prefix, n_parts.suffix] if p]
                name = ' '.join(parts).strip()
            
            if not name:
                name = "Unknown Contact (VCF Import)"


            # 2. Get Phone Number (Prioritize CELL, then HOME, then first available TEL)
            if hasattr(vcard, 'tel_list'):
                preferred_phone = ""
                backup_phone = ""
                for tel in vcard.tel_list:
                    # Clean up phone value
                    p_value = str(tel.value).strip()
                    
                    if 'CELL' in tel.params.get('TYPE', []):
                        preferred_phone = p_value
                        break # Found the best type, stop searching
                    elif not backup_phone and ('HOME' in tel.params.get('TYPE', []) or 'VOICE' in tel.params.get('TYPE', [])):
                         backup_phone = p_value # Store a decent backup
                    elif not preferred_phone:
                        preferred_phone = p_value # Store first number as default
                
                phone = preferred_phone if preferred_phone else backup_phone


            # 3. Get Email (First available 'EMAIL')
            if hasattr(vcard, 'email_list') and vcard.email_list:
                email = str(vcard.email_list[0].value).strip()
                
            
            # Save the contact only if a valid phone number or email is found
            if phone or email:
                contacts_collection.insert_one({
                    "user_id": current_user_id,
                    "name": name,
                    "phone": phone, # Phone might be empty if only email found
                    "email": email, # Email might be empty if only phone found
                    "source": "vcf_import",
                    "created_at": datetime.utcnow()
                })
                contacts_imported += 1
            
        if contacts_imported > 0:
            return jsonify({
                "success": True, 
                "message": f"Successfully imported {contacts_imported} contact(s) from {filename}."
            }), 200
        else:
            return jsonify({
                "success": False, 
                "message": "No valid contacts found in the VCF file (0 phone numbers/emails extracted)."
            }), 400

    except Exception as e:
        logging.error(f"❌ Error during VCF parsing for {filename}: {e}")
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
                # Safely format datetime object
                "created_at": contact.get('created_at', datetime.now()).strftime("%Y-%m-%d %H:%M:%S")
            })
            
        return jsonify({"success": True, "contacts": contacts_list})
    
    except Exception as e:
        logging.error(f"❌ Error fetching contacts: {e}")
        return jsonify({"success": False, "message": "Failed to retrieve contacts."}), 500

@app.route('/api/contacts/<contact_id>', methods=['DELETE'])
@login_required
def delete_contact(contact_id):
    current_user_id = session.get('user_id')
    
    try:
        if not ObjectId.is_valid(contact_id):
            return jsonify({"success": False, "message": "Invalid Contact ID format."}), 400
            
        result = contacts_collection.delete_one({"_id": ObjectId(contact_id), "user_id": current_user_id})
        
        if result.deleted_count == 1:
            return jsonify({"success": True, "message": "Contact deleted successfully."})
        else:
            return jsonify({"success": False, "message": "Contact not found or unauthorized."}), 404
    
    except Exception as e:
        logging.error(f"❌ Error deleting contact {contact_id}: {e}")
        return jsonify({"success": False, "message": "Failed to delete contact."}), 500

# --- 5. STATIC FILE ROUTES ---

@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/<path:filename>')
def serve_static(filename):
    if filename in ['app.py', '.env', 'gallery.py']:
        return "Access Denied", 403
    return send_from_directory(app.static_folder, filename)

if __name__ == '__main__':
    logging.info("-------------------------------------------------------")
    logging.info("  Akshu Cloud Gallery Backend Server Starting...")
    logging.info("-------------------------------------------------------")
    app.run(host='0.0.0.0', port=5000)