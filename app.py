# app.py - Akshu Cloud Gallery Backend (Multi-User Secured)

from flask import Flask, request, jsonify, session, send_from_directory, redirect, url_for
from flask_bcrypt import Bcrypt
from flask_session import Session
from datetime import datetime
import os
import io
from dotenv import load_dotenv

# Database and Cloudinary Imports
from pymongo import MongoClient, errors
from bson.objectid import ObjectId
import cloudinary
import cloudinary.uploader
from cloudinary.utils import cloudinary_url

# Load environment variables from .env file
load_dotenv()

# --- 1. CONFIGURATION & INITIALIZATION ---
app = Flask(__name__, static_folder='.') # static_folder='.' means it serves files from the current directory

# Load configuration variables from .env
MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("DB_NAME")
SECRET_KEY = os.getenv("SECRET_KEY")

CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET")

# Check for critical configuration
if not all([MONGO_URI, DB_NAME, SECRET_KEY, CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET]):
    print("\n❌ ERROR: .env file is missing or values are empty. Please check your configuration.")
    exit(1)

# Configure Flask App for Session Management
app.config['SECRET_KEY'] = SECRET_KEY
app.config['SESSION_TYPE'] = 'filesystem' # Simple session storage
Session(app)

# Initialize extensions
bcrypt = Bcrypt(app)

# Initialize MongoDB
client = MongoClient(MONGO_URI)
db = client[DB_NAME]
users_collection = db['users']
photos_collection = db['photos']

# Initialize Cloudinary
cloudinary.config(
    cloud_name=CLOUDINARY_CLOUD_NAME,
    api_key=CLOUDINARY_API_KEY,
    api_secret=CLOUDINARY_API_SECRET
)

# --- 2. AUTHENTICATION ROUTES ---

@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({"success": False, "message": "Username and password are required."}), 400

    # Check if user already exists
    if users_collection.find_one({'username': username}):
        return jsonify({"success": False, "message": "Username already exists."}), 409

    # Hash the password securely
    hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
    
    # Save user to database
    users_collection.insert_one({'username': username, 'password': hashed_password})
    print(f"✅ User {username} registered successfully.")

    return jsonify({"success": True, "message": "Registration successful. Please log in."})

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    user = users_collection.find_one({'username': username})

    if user and bcrypt.check_password_hash(user['password'], password):
        # Set session variable for authentication
        session['username'] = username
        print(f"✅ User {username} logged in.")
        return jsonify({"success": True, "message": "Login successful.", "username": username})
    else:
        return jsonify({"success": False, "message": "Invalid username or password."}), 401

@app.route('/api/logout', methods=['POST'])
def logout():
    session.pop('username', None)
    return jsonify({"success": True, "message": "Logout successful."})

@app.route('/api/status', methods=['GET'])
def get_status():
    """Checks if the user is currently logged in."""
    is_logged_in = 'username' in session
    username = session.get('username', 'Guest')
    return jsonify({"isLoggedIn": is_logged_in, "username": username})

# --- 3. GALLERY ROUTES (SECURED FOR MULTI-USER) ---

@app.route('/api/upload', methods=['POST'])
def upload_photo():
    # 1. Security Check: Is user logged in?
    if 'username' not in session:
        return jsonify({"success": False, "message": "Login required to upload."}), 401

    if 'file' not in request.files:
        return jsonify({"success": False, "message": "No file part"}), 400

    file_to_upload = request.files['file']
    current_username = session['username']
    
    try:
        # 2. Upload to Cloudinary, use username as a unique folder
        # This keeps user photos separated on Cloudinary.
        folder_name = f"gallery/{current_username}"
        upload_result = cloudinary.uploader.upload(
            file_to_upload,
            folder=folder_name, 
            resource_type="auto"
        )
        print(f"Cloudinary upload successful. Public ID: {upload_result['public_id']}")

        # 3. Save metadata to MongoDB, linking it to the current user
        photos_collection.insert_one({
            "url": upload_result['secure_url'],
            "public_id": upload_result['public_id'],
            "filename": file_to_upload.filename,
            "uploaded_by": current_username, # CRITICAL: Link photo to user
            "timestamp": datetime.now()
        })
        
        return jsonify({"success": True, "message": "Photo uploaded successfully."})
        
    except cloudinary.exceptions.Error as e:
        print(f"❌ Cloudinary Upload Error: {e}")
        return jsonify({"success": False, "message": f"Cloudinary upload failed: {str(e)}"}), 500
    except Exception as e:
        print(f"❌ General Upload Error: {e}")
        return jsonify({"success": False, "message": f"Upload failed: {str(e)}"}), 500


@app.route('/api/photos', methods=['GET'])
def get_photos():
    # 1. Security Check: Is user logged in?
    if 'username' not in session:
        return jsonify({"success": False, "message": "Login required."}), 401
    
    current_username = session['username']
    
    try:
        # 2. Fetch only photos uploaded by the logged-in user
        photos = photos_collection.find({"uploaded_by": current_username}).sort("timestamp", -1)
        
        # Convert MongoDB BSON objects to JSON-serializable list
        photos_list = []
        for photo in photos:
            photos_list.append({
                "id": str(photo['_id']),
                "url": photo['url'],
                "public_id": photo['public_id'],
                "filename": photo.get('filename', 'Unknown'),
                "timestamp": photo['timestamp'].isoformat()
            })
            
        return jsonify({"success": True, "photos": photos_list})
    
    except errors.PyMongoError as e:
        print(f"❌ MongoDB Fetch Error: {e}")
        return jsonify({"success": False, "message": "Could not fetch photos from database."}), 500


@app.route('/api/delete/<photo_id>', methods=['DELETE'])
def delete_photo(photo_id):
    # 1. Security Check: Is user logged in?
    if 'username' not in session:
        return jsonify({"success": False, "message": "Login required."}), 401

    current_username = session['username']
    
    try:
        # 2. Find photo and ensure it belongs to the logged-in user
        photo_data = photos_collection.find_one({"_id": ObjectId(photo_id), "uploaded_by": current_username})
        
        if not photo_data:
            return jsonify({"success": False, "message": "Photo not found or unauthorized access."}), 403 # Important security check
        
        public_id = photo_data['public_id']
        
        # 3. Delete from Cloudinary
        cloudinary.uploader.destroy(public_id)
        print(f"Cloudinary deletion successful for public ID: {public_id}")

        # 4. Delete from MongoDB
        photos_collection.delete_one({"_id": ObjectId(photo_id)})
        print(f"MongoDB photo ID {photo_id} deleted.")

        return jsonify({"success": True, "message": "Photo deleted successfully."})

    except Exception as e:
        print(f"❌ General Delete Error for photo {photo_id} by user {current_username}: {e}")
        return jsonify({"success": False, "message": f"Deletion failed: {str(e)}"}), 500


# --- 4. STATIC FILE ROUTES (Serving HTML/CSS/JS) ---

@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/<path:filename>')
def serve_static(filename):
    """Serves all static files (HTML, CSS, JS, etc.) from the current directory."""
    # Ensure it doesn't serve non-static files like app.py or .env
    if filename in ['app.py', '.env']:
        return "Access Denied", 403
    return send_from_directory(app.static_folder, filename)

if __name__ == '__main__':
    print("-------------------------------------------------------")
    print("         Akshu Cloud Gallery is starting...")
    print(f"Database: {DB_NAME}")
    print(f"Cloudinary Cloud: {CLOUDINARY_CLOUD_NAME}")
    print("-------------------------------------------------------")
    app.run(debug=True)