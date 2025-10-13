# app.py (FINALIZED with new endpoints)
import sys
from pymongo import MongoClient
from bson.objectid import ObjectId
import bcrypt
from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime
from pymongo.errors import PyMongoError # NEW IMPORT

# --- Initialize Flask App ---
app = Flask(__name__)
CORS(app) 
MONGO_URI = "mongodb+srv://devansh01:deVansh%4001@cluster0.jsla8b0.mongodb.net/"

# --- Database Connection ---
def connect_to_mongodb():
    """Establishes connection to the MongoDB server and two collections (users and groups)."""
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        db = client["student_network_db"]
        client.admin.command('ping') 
        
        users_collection = db["users"]
        users_collection.create_index("email", unique=True)
        groups_collection = db["groups"]
        groups_collection.create_index("project_name", unique=True) 

        print("✅ Database connection successful and collections ready.")
        return users_collection, groups_collection
        
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        sys.exit(1)

users_collection, groups_collection = connect_to_mongodb()

# --- Helper Functions ---
def hash_password(password):
    """Hashes the password using bcrypt for secure storage."""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

# === NEW HELPER FUNCTION: Get User's Team (Existing) ===
def get_user_team(user_id):
    """
    Finds and returns the simplified data for the first group a user belongs to.
    Returns None if no team is found.
    """
    try:
        # Search for any group where the user's ID is in the members list
        team = groups_collection.find_one({"members": user_id}) 
        
        if team:
            # Construct simplified team data
            return {
                "groupId": str(team['_id']),
                "teamName": team.get('project_name'),
                "projectDescription": team.get('description_objective'),
                "teamSize": team.get('preferred_team_size'),
                # Convert list of skills to comma-separated string for client-side consumption
                "skillsNeeded": ",".join(team.get('required_skills', [])), 
                "timeline": team.get('project_timeline')
            }
        return None
    except Exception as e:
        print(f"⚠️ Error checking user team status: {e}")
        return None

# =========================================================
#  USER AUTHENTICATION & PROFILE ENDPOINTS (Existing)
# =========================================================

@app.route('/signup', methods=['POST'])
def signup_api():
    try:
        data = request.get_json()
        full_name = data.get('fullName')
        email = data.get('email', '').lower()
        password = data.get('password')
        
        if not full_name or not email or not password:
            return jsonify({"error": "Missing required fields (Full Name, Email, Password)."}), 400

        if users_collection.find_one({"email": email}):
            return jsonify({"error": "Account with this email already exists."}), 409

        user_data = { 
            "full_name": full_name, 
            "email": email, 
            "password": hash_password(password),
            "college": data.get('university'), 
            "department": data.get('branch'), 
            "year_of_study": data.get('academicYear'), 
            "skills": data.get('skills', []), 
            "bio": "Highly motivated student.",          
            "phone": "Not Provided",                  
            "interests": [],                          
            "linkedin": "Add Link",                   
            "github": "Add Link",                     
            "profile_photo_b64": None,                
            "created_at": datetime.utcnow() 
        }
        users_collection.insert_one(user_data)
        return jsonify({"message": f"Account created for {full_name}!"}), 201
    except Exception as e:
        print(f"💥 An unexpected signup error occurred: {e}")
        return jsonify({"error": "An internal server error occurred during signup."}), 500

@app.route('/login', methods=['POST'])
def login_api():
    """API endpoint to handle user login, return profile data, and team status."""
    try:
        data = request.get_json()
        email = data.get('email', '').lower()
        password = data.get('password')

        if not email or not password:
            return jsonify({"error": "Email and password are required."}), 400

        user = users_collection.find_one({"email": email})

        if user and bcrypt.checkpw(password.encode('utf-8'), user['password']):
            user_id_str = str(user['_id'])
            
            # --- Check for team affiliation here ---
            current_team_data = get_user_team(user_id_str)
            # ------------------------------------------------
            
            user_profile = { 
                "id": user_id_str, 
                "fullName": user.get('full_name'),
                "email": user.get('email'),
                "college": user.get('college'),
                "department": user.get('department'),
                "year_of_study": user.get('year_of_study'),
                "skills": user.get('skills', []),
                "bio": user.get('bio'), 
                "phone": user.get('phone'),
                "interests": user.get('interests', []), 
                "linkedin": user.get('linkedin'),
                "github": user.get('github'),
                "profilePhotoUrl": user.get('profile_photo_b64')
            }
            
            return jsonify({
                "message": f"Welcome back, {user['full_name']}!",
                "user": user_profile,
                "currentTeam": current_team_data # Include team data in the login response
            }), 200
        else:
            return jsonify({"error": "Invalid email or password."}), 401 

    except Exception as e:
        print(f"💥 An unexpected login error occurred: {e}")
        return jsonify({"error": "An internal server error occurred."}), 500

# === Check if user is already in a team (Existing) ===
@app.route('/check_team_status', methods=['POST'])
def check_team_status_api():
    """
    Checks the 'groups' collection to see if a user is a member of any team.
    Returns the first found team data if they are a member.
    """
    try:
        data = request.get_json()
        user_id = data.get('user_id')

        if not user_id:
            return jsonify({"error": "Missing user ID."}), 400
        
        team_data = get_user_team(user_id) # Reuse the helper function
        
        if team_data:
            return jsonify({
                "hasTeam": True,
                "team": team_data
            }), 200
        else:
            return jsonify({"hasTeam": False}), 200

    except Exception as e:
        print(f"💥 An unexpected team status error occurred: {e}")
        return jsonify({"error": "An internal server error occurred."}), 500

# =========================================================
#  PROFILE/GROUP ENDPOINTS (Existing)
# =========================================================

@app.route('/upload_profile_photo', methods=['POST'])
def upload_profile_photo_api():
    """
    API endpoint to receive Base64 photo string and save it to MongoDB.
    """
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        photo_b64 = data.get('photo_b64')

        if not user_id or not photo_b64:
            return jsonify({"error": "Missing user ID or photo data."}), 400

        result = users_collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"profile_photo_b64": photo_b64}}
        )

        if result.matched_count == 0:
            return jsonify({"error": "User not found."}), 404
        
        print(f"✅ User ID {user_id} profile photo updated.")
        
        return jsonify({
            "message": "Profile photo updated successfully.",
            "photo_url": photo_b64 
        }), 200

    except Exception as e:
        print(f"💥 An unexpected photo upload error occurred: {e}", file=sys.stderr) 
        return jsonify({"error": "An internal server error occurred during photo upload."}), 500

@app.route('/update_profile', methods=['PUT'])
def update_profile_api():
    """API endpoint to update user profile details in MongoDB based on ID."""
    try:
        data = request.get_json()
        user_id = data.get('id')
        update_fields = data.get('updates', {})
        
        if not user_id or not update_fields:
            return jsonify({"error": "Missing user ID or update fields."}), 400

        allowed_fields = {
            "fullName": "full_name",
            "department": "department",
            "year_of_study": "year_of_study",
            "bio": "bio",
            "phone": "phone",
            "interests": "interests",
            "linkedin": "linkedin",
            "github": "github"
        }

        mongo_updates = {}
        for frontend_key, backend_key in allowed_fields.items():
            if frontend_key in update_fields:
                mongo_updates[backend_key] = update_fields[frontend_key]

        if not mongo_updates:
             return jsonify({"error": "No valid fields provided for update."}), 400

        result = users_collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": mongo_updates}
        )

        if result.matched_count == 0:
            return jsonify({"error": "User not found."}), 404
        
        print(f"✅ User ID {user_id} updated successfully with: {mongo_updates}")
        return jsonify({"message": "Profile updated successfully."}), 200

    except Exception as e:
        print(f"💥 An unexpected profile update error occurred: {e}")
        return jsonify({"error": "An internal server error occurred during profile update."}), 500

@app.route('/create_group', methods=['POST'])
def create_group_api():
    """API endpoint to create a new project group and save it to MongoDB."""
    try:
        data = request.get_json()
        project_name = data.get('teamName')
        description = data.get('projectDescription')
        team_size = data.get('teamSize')
        skills_needed_input = data.get('skillsNeeded')
        timeline = data.get('timeline')
        user_id = data.get('userId')

        if not project_name or not description or not user_id:
            return jsonify({"error": "Team Name, Project Description, and User ID are required."}), 400

        required_skills = [skill.strip() for skill in skills_needed_input.split(',') if skill.strip()] if skills_needed_input else []

        group_document = {
            "project_name": project_name,
            "description_objective": description,
            "required_skills": required_skills,
            "preferred_team_size": team_size,
            "project_timeline": timeline,
            "creator_user_id": user_id, 
            "members": [user_id], 
            "status": "Recruiting",
            "date_created": datetime.utcnow()
        }

        result = groups_collection.insert_one(group_document)
        
        print(f"✅ Group '{project_name}' created by user {user_id} with ID: {result.inserted_id}")
        return jsonify({
            "message": f"Team '{project_name}' created successfully!",
            "groupId": str(result.inserted_id)
        }), 201

    except Exception as e:
        if 'duplicate key error' in str(e):
             return jsonify({"error": f"A team with the name '{project_name}' already exists. Please choose a different name."}), 409
        
        print(f"💥 An unexpected group creation error occurred: {e}")
        return jsonify({"error": "An internal server error occurred during group creation."}), 500

# =========================================================
#  NEW GROUP/POST ENDPOINTS (NEWLY ADDED)
# =========================================================

@app.route('/get_available_groups', methods=['POST'])
def get_available_groups_api():
    """
    Fetches groups a user can join (i.e., not already a member and not full).
    Also includes the creator's name.
    """
    try:
        data = request.get_json()
        user_id = data.get('user_id')

        if not user_id:
            return jsonify({"error": "Missing user ID."}), 400
        
        # 1. Find all groups where the user is NOT in the members list
        # We search for the string version of the user_id.
        available_groups_cursor = groups_collection.find({
            "members": {"$ne": user_id}
        })
        
        groups_list = []
        # Gather all creator IDs to fetch names in one go
        creator_ids = list(set(g.get('creator_user_id') for g in available_groups_cursor.clone()))

        # Fetch creator names map
        creator_names = {}
        # Fetch only the users whose IDs are in the creator_ids list
        for creator_doc in users_collection.find({"_id": {"$in": [ObjectId(cid) for cid in creator_ids if ObjectId.is_valid(cid)]}}):
             creator_names[str(creator_doc.get('_id'))] = creator_doc.get('full_name', 'Unknown')


        for group in available_groups_cursor:
            # Check if the team is not full (simple check based on max size)
            preferred_size = group.get('preferred_team_size', '4-5').split('-')[-1].replace('+', '')
            max_members = int(preferred_size) if preferred_size.isdigit() else 5
            
            if len(group.get('members', [])) < max_members:
                groups_list.append({
                    "groupId": str(group['_id']),
                    "project_name": group.get('project_name'),
                    "description_objective": group.get('description_objective'),
                    "required_skills": group.get('required_skills', []),
                    "preferred_team_size": group.get('preferred_team_size'),
                    "project_timeline": group.get('project_timeline'),
                    "creator_user_id": group.get('creator_user_id'),
                    "members": group.get('members', []),
                    "creator_name": creator_names.get(group.get('creator_user_id'), 'Unknown')
                })

        return jsonify({"groups": groups_list}), 200

    except Exception as e:
        print(f"💥 Error fetching available groups: {e}")
        return jsonify({"error": "An internal server error occurred."}), 500

@app.route('/join_group', methods=['POST'])
def join_group_api():
    """
    Adds a user to a group's members list.
    """
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        group_id = data.get('group_id')

        if not user_id or not group_id:
            return jsonify({"error": "Missing user ID or group ID."}), 400

        # Check for existing team affiliation (critical business logic)
        existing_team = groups_collection.find_one({"members": user_id})
        if existing_team:
            return jsonify({"error": "You are already a member of a team. Please leave your current team first."}), 403

        # 1. Check if the group exists and is not full
        group_to_join = groups_collection.find_one({"_id": ObjectId(group_id)})
        if not group_to_join:
            return jsonify({"error": "Group not found."}), 404

        preferred_size = group_to_join.get('preferred_team_size', '4-5').split('-')[-1].replace('+', '')
        max_members = int(preferred_size) if preferred_size.isdigit() else 5

        if len(group_to_join.get('members', [])) >= max_members:
            return jsonify({"error": "This team is already full."}), 403
            
        # 2. Add user to the members list
        result = groups_collection.update_one(
            {"_id": ObjectId(group_id)},
            {"$push": {"members": user_id}}
        )

        if result.matched_count == 0:
            return jsonify({"error": "Group not found during update."}), 404
        
        print(f"✅ User {user_id} joined group {group_id}.")
        return jsonify({"message": "Successfully joined the group!"}), 200

    except PyMongoError as e:
        print(f"💥 MongoDB error during join_group: {e}")
        return jsonify({"error": "Database error during join process."}), 500
    except Exception as e:
        print(f"💥 An unexpected error occurred during join_group: {e}")
        return jsonify({"error": "An internal server error occurred."}), 500


# =========================================================
#  Main Runner (Existing)
# =========================================================
if __name__ == "__main__":
    print("🚀 Starting The Huddle Server on http://127.0.0.1:5000")
    app.run(host='127.0.0.1', port=5000, debug=True)