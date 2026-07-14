import streamlit as st
import pandas as pd
import json
from services.db_service import db_service
from services.ai_service import triage_incident, chat_with_copilot, load_stadium_context
from services.weather_service import get_live_weather
from services.geocoding import geocode_city, get_ip_location
from streamlit_geolocation import streamlit_geolocation

@st.cache_data(ttl=5)
def get_all_users_cached():
    return db_service.get_all_users()

@st.cache_data(ttl=5)
def get_all_tickets_cached():
    return db_service.get_all_tickets()


st.set_page_config(
    page_title="VenueOps Copilot | FIFA 2026",
    page_icon="🏟️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for ticket cards (removed background-color to fix dark mode)
st.markdown("""
<style>
    .ticket-card {
        padding: 15px;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(255,255,255,0.1);
        margin-bottom: 10px;
        border-left: 5px solid #0055a4;
        background-color: rgba(128, 128, 128, 0.1); /* Slight contrast that works in light/dark mode */
    }
    .ticket-card h4 { margin-top: 0; }
    .priority-High, .priority-Critical { border-left-color: #dc3545; }
    .priority-Medium { border-left-color: #ffc107; }
    .priority-Low { border-left-color: #28a745; }
    .status-Resolved { opacity: 0.6; border-left-color: #6c757d; }
</style>
""", unsafe_allow_html=True)

# Helper to update the mock JSON for dynamic attendance
def update_attendance(new_count):
    try:
        with open("data/stadium_state.json", "r") as f:
            data = json.load(f)
        data["current_attendance"] = new_count
        with open("data/stadium_state.json", "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        st.error(f"Failed to update attendance: {e}")


# ----------------- AUTHENTICATION -----------------
if "user" not in st.session_state:
    st.session_state["user"] = None
if "login_attempts" not in st.session_state:
    st.session_state["login_attempts"] = {}
if "otp_verified_for" not in st.session_state:
    st.session_state["otp_verified_for"] = None

def show_login_screen():
    st.title("🏟️ VenueOps Copilot - Login")
    
    users = get_all_users_cached()
    if users == "QUOTA_EXCEEDED":
        st.error("Firebase database quota exhausted. Please try again tomorrow at 12:00 AM PST (when the daily quota resets).")
        return
    elif not users:
        st.error("No users found in database.")
        return
        
    # Make the mapping case insensitive so 'admin' works with uppercase input
    user_map = {u['id'].upper(): u for u in users}
    
    # OTP Reset UI
    if st.session_state["otp_verified_for"]:
        emp_id = st.session_state["otp_verified_for"]
        st.success(f"OTP Verified for {emp_id}. Please enter your new password.")
        with st.form("new_password_form"):
            new_password = st.text_input("New Password", type="password")
            confirm_password = st.text_input("Confirm Password", type="password")
            if st.form_submit_button("Reset Password", type="primary"):
                if new_password and new_password == confirm_password:
                    db_service.update_user(emp_id, {"password": new_password})
                    st.success("Password reset successfully! Please log in.")
                    st.session_state["otp_verified_for"] = None
                    st.session_state["login_attempts"][emp_id.upper()] = 0
                    st.rerun()
                else:
                    st.error("Passwords do not match.")
        return

    st.markdown("Please log in using your Employee ID and Password.")
    
    st.info("""
    **💡 Hackathon Demo Credentials:**
    - **Admin:** `admin` | Password: `password123`
    - **Manager:** `EMP001` | Password: `password123`
    - **Staff:** `EMP011` | Password: `password123`
    """)
    
    with st.form("login_form"):
        emp_id = st.text_input("Employee ID").strip().upper()
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Log In", type="primary")
        
        if submitted:
            if emp_id in user_map:
                user = user_map[emp_id]
                attempts = st.session_state["login_attempts"].get(emp_id, 0)
                
                if attempts >= 3:
                    st.error("Account locked due to too many failed attempts.")
                elif user.get("password") == password:
                    st.session_state["user"] = user
                    st.session_state["login_attempts"][emp_id] = 0 # reset on success
                    st.rerun()
                else:
                    st.session_state["login_attempts"][emp_id] = attempts + 1
                    remaining = 3 - st.session_state["login_attempts"][emp_id]
                    if remaining > 0:
                        st.error(f"Incorrect Password. {remaining} attempts remaining.")
                    else:
                        st.error("Account locked due to too many failed attempts.")
            else:
                st.error("Employee ID not found.")
                
    # Show OTP unlock if locked
    if emp_id and st.session_state["login_attempts"].get(emp_id, 0) >= 3:
        st.warning("⚠️ Your account is locked. Please reset your password via OTP, or contact your System Admin.")
        
        if st.session_state.get("otp_sent_to") != emp_id:
            if st.button("Send Mobile OTP"):
                st.session_state["otp_sent_to"] = emp_id
                st.rerun()
        else:
            with st.form("otp_form"):
                st.success(f"OTP sent to registered mobile for {emp_id}.")
                st.info("For this demo, the expected OTP is '1234'.")
                otp = st.text_input("Enter Mobile OTP")
                if st.form_submit_button("Verify OTP"):
                    if otp == "1234":
                        true_id = user_map[emp_id]["id"] if emp_id in user_map else emp_id
                        st.session_state["otp_verified_for"] = true_id
                        st.session_state["otp_sent_to"] = None
                        st.rerun()
                    else:
                        st.error("Invalid OTP.")

if st.session_state["user"] is None:
    show_login_screen()
    st.stop()
    
# If we reach here, user is logged in
logged_in_user = st.session_state["user"]
is_admin = logged_in_user.get("role") == "Admin"
is_manager = logged_in_user.get("role") == "Manager"

# ----------------- SIDEBAR CONTEXT -----------------
with st.sidebar:
    st.title("🏟️ Stadium Context")

    st.markdown("---")
    st.markdown(f"**Logged in as:** {logged_in_user['name']}")
    st.markdown(f"**Role:** {logged_in_user['role']}")
    if st.button("Log Out"):
        st.session_state["user"] = None
        st.rerun()
    st.markdown("---")
    
    stadium_state, _ = load_stadium_context()
    if stadium_state:
        import datetime
        start_time_iso = stadium_state.get('match_start_time')
        current_attendance = 0
        fill_percentage = 0.0
        if start_time_iso:
            try:
                start_dt = datetime.datetime.fromisoformat(start_time_iso)
                now = datetime.datetime.now(datetime.timezone.utc)
                if now >= start_dt:
                    current_attendance = 100000
                    fill_percentage = 1.0
                else:
                    time_remaining = (start_dt - now).total_seconds()
                    elapsed_in_window = 1800 - time_remaining
                    if elapsed_in_window < 0:
                        current_attendance = 0
                        fill_percentage = 0.0
                    else:
                        fill_percentage = elapsed_in_window / 1800
                        current_attendance = int(100000 * fill_percentage)
            except Exception:
                current_attendance = stadium_state.get('current_attendance', 0)
        else:
            current_attendance = stadium_state.get('current_attendance', 0)
            
        st.metric("Current Attendance", f"{current_attendance:,}")
        import datetime
        import streamlit.components.v1 as components
        
        start_time_iso = stadium_state.get('match_start_time')
        if start_time_iso:
            # Parse and format the start time nicely
            try:
                start_dt = datetime.datetime.fromisoformat(start_time_iso)
                start_dt_local = start_dt.astimezone()
                st.write(f"**Match Start:** {start_dt_local.strftime('%I:%M %p')}")
                
                # Live Javascript Countdown
                countdown_html = f"""
                <div style="font-family: sans-serif; padding: 10px; background-color: rgba(128,128,128,0.1); border-radius: 8px; border-left: 5px solid #0055a4;">
                    <div style="font-size: 0.9em; font-weight: bold; color: gray; margin-bottom: 5px;">Time to Kickoff</div>
                    <div id="countdown" style="font-size: 1.5em; font-weight: bold;">Loading...</div>
                </div>
                <script>
                    var countDownDate = new Date("{start_time_iso}").getTime();
                    var matchDurationMs = 3 * 60 * 60 * 1000; // 3 hours in milliseconds
                    
                    var x = setInterval(function() {{
                        var now = new Date().getTime();
                        var distance = countDownDate - now;
                        
                        if (distance < -matchDurationMs) {{
                            clearInterval(x);
                            document.getElementById("countdown").innerHTML = "MATCH ENDED";
                            document.getElementById("countdown").style.color = "gray";
                        }} else if (distance < 0) {{
                            clearInterval(x);
                            document.getElementById("countdown").innerHTML = "MATCH IN PROGRESS";
                            document.getElementById("countdown").style.color = "#dc3545";
                        }} else {{
                            var hours = Math.floor((distance % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
                            var minutes = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60));
                            var seconds = Math.floor((distance % (1000 * 60)) / 1000);
                            
                            var text = "";
                            if (hours > 0) text += hours + "h ";
                            text += minutes + "m " + seconds + "s";
                            document.getElementById("countdown").innerHTML = text;
                        }}
                    }}, 1000);
                </script>
                """
                components.html(countdown_html, height=100)
            except Exception as e:
                st.metric("Time to Kickoff", stadium_state.get('time_to_kickoff', 'N/A'))
        else:
            st.metric("Time to Kickoff", stadium_state.get('time_to_kickoff', 'N/A'))
        
        st.subheader("Gate Status")
        if fill_percentage < 0.2:
            dynamic_gate_status = {"Gate A": "Low Traffic", "Gate B": "Low Traffic", "Gate C": "Low Traffic", "Gate D": "Closed"}
        elif fill_percentage < 0.5:
            dynamic_gate_status = {"Gate A": "Moderate Traffic", "Gate B": "Low Traffic", "Gate C": "Moderate Traffic", "Gate D": "Closed"}
        elif fill_percentage < 0.8:
            dynamic_gate_status = {"Gate A": "High Traffic", "Gate B": "Moderate Traffic", "Gate C": "High Traffic (Bottleneck Detected)", "Gate D": "Low Traffic"}
        elif fill_percentage < 0.95:
            dynamic_gate_status = {"Gate A": "High Traffic", "Gate B": "High Traffic", "Gate C": "High Traffic", "Gate D": "Moderate Traffic"}
        elif fill_percentage < 1.0:
            dynamic_gate_status = {"Gate A": "Clearing", "Gate B": "Clearing", "Gate C": "Clearing", "Gate D": "Clearing"}
        else:
            dynamic_gate_status = {"Gate A": "Closed (Match Started)", "Gate B": "Closed (Match Started)", "Gate C": "Closed (Match Started)", "Gate D": "Closed (Match Started)"}
            
        for gate, status in dynamic_gate_status.items():
            color = "green" if "Low" in status or "Clearing" in status else "orange" if "Moderate" in status else "gray" if "Closed" in status else "red"
            st.markdown(f"**{gate}:** :{color}[{status}]")
            
        st.subheader("📍 Location & Live Weather")
        # Render a geolocation button so the browser can ask the user for location permission
        st.caption("Click the 🎯 button below to get local weather!")
        loc = streamlit_geolocation()
        
        manual_city = st.text_input("Or enter city manually (if blocked):", placeholder="e.g. Chennai, India")
        
        lat, lon = None, None
        display_city = None
        if manual_city:
            lat, lon, display_city = geocode_city(manual_city)
        elif loc and loc.get('latitude') and loc.get('longitude'):
            lat = loc['latitude']
            lon = loc['longitude']
        else:
            # AUTOMATIC FALLBACK: Use IP to get location seamlessly
            client_ip = None
            try:
                if hasattr(st, "context") and hasattr(st.context, "headers"):
                    client_ip = st.context.headers.get("X-Forwarded-For", "").split(",")[0].strip() or None
            except:
                pass
            lat, lon, display_city = get_ip_location(client_ip)
            
        weather = get_live_weather(lat, lon)
        if display_city:
            weather['city'] = display_city
        
        # Display dynamically fetched city instead of hardcoded stadium state venue
        st.write(f"**{weather.get('city', stadium_state.get('venue'))}**")
        st.write(f"{weather['icon']} {weather['condition']} ({weather['temperature_c']}°C)")
    else:
        st.error("Failed to load stadium context.")

# ----------------- MAIN CONTENT -----------------
st.title("🏟️ VenueOps Copilot")
st.markdown("AI-driven operational intelligence for stadium managers.")
st.info("💡 **How to use:** To report a new incident, go to the **Triage & Operations Copilot** tab and describe the issue (e.g., *'There is a huge spill at Gate A'*). To resolve an incident, click **Mark Resolved** below.")


tab1, tab2, tab3, tab4 = st.tabs(["📋 Incident Board (Kanban)", "💬 Triage & Operations Copilot", "👥 Workforce Roster", "⚙️ Settings"])

# --- TAB 1: INCIDENT BOARD ---
with tab1:
    col1, col2 = st.columns([4, 1])
    with col1:
        st.subheader("Active Incidents")
    with col2:
        if st.button("🔄 Refresh Data"):
            st.rerun()


    raw_tickets = get_all_tickets_cached()
    tickets = raw_tickets
    
    if is_manager:
        view_filter = st.radio("Ticket View:", ["All Tickets", "My Team's Tickets"], horizontal=True)
        if view_filter == "My Team's Tickets":
            tickets = []
            for t in raw_tickets:
                if t.get("escalation_contact") == logged_in_user["name"]:
                    tickets.append(t)
                elif isinstance(t.get("assigned_employee"), dict) and t.get("assigned_employee").get("reporting_to") == logged_in_user["name"]:
                    tickets.append(t)
    elif not is_admin:
        view_filter = st.radio("Ticket View:", ["All Tickets", "Assigned to Me"], horizontal=True)
        if view_filter == "Assigned to Me":
            tickets = [t for t in raw_tickets if isinstance(t.get("assigned_employee"), dict) and t.get("assigned_employee").get("id") == logged_in_user["id"]]
    
    if is_admin or is_manager:
        st.markdown("---")
        st.write("🔍 **Advanced Filters**")
        all_users_for_filter = get_all_users_cached()
        if is_manager:
            all_users_for_filter = [u for u in all_users_for_filter if u.get("reporting_to") == logged_in_user["name"]]
        
        filter_options = ["All"] + sorted(list(set(u["name"] for u in all_users_for_filter)))
        selected_assignee = st.selectbox("Filter by Assignee:", filter_options)
        
        if selected_assignee != "All":
            tickets = [t for t in tickets if isinstance(t.get("assigned_employee"), dict) and t.get("assigned_employee").get("name") == selected_assignee]
            
    if not tickets:
        st.info("No incidents reported. The stadium is secure.")
    else:
        # Create columns for Open vs Resolved
        open_col, resolved_col = st.columns(2)
        
        open_tickets = [t for t in tickets if t.get("status") in ["Open", "Escalated"]]
        resolved_tickets = [t for t in tickets if t.get("status") == "Resolved"]
        
        with open_col:
            st.markdown(f"### 🔴 Open / Escalated ({len(open_tickets)})")
            for t in open_tickets:
                severity = t.get("severity", "Low")
                assigned = t.get("assigned_employee")
                assigned_text = "Pending Assignment"
                if assigned:
                    contact_info = assigned.get('contact') or assigned.get('phone_number') or "No Contact"
                    assigned_text = f"{assigned.get('name')} ({assigned.get('role')}) - {contact_info}"
                    
                status_icon = "🚨 ESCALATED" if t.get("status") == "Escalated" else "🔴 OPEN"
                
                st.markdown(f"""
                <div class="ticket-card priority-{severity}">
                    <h4>{t.get('id')} - {t.get('incident_type')} <span style="font-size: 0.8em; color: {'#dc3545' if t.get('status') == 'Escalated' else 'inherit'};">[{status_icon}]</span></h4>
                    <p><strong>Location:</strong> {t.get('location')} (Bldg: {t.get('building', 'Unknown')}, Fl: {t.get('floor', 'Unknown')})<br/>
                    <strong>Severity:</strong> {severity} <span style="float: right; font-weight: bold; color: #dc3545;">⏱️ SLA: {t.get('sla', 'N/A')}</span><br/>
                    <strong>Action:</strong> {t.get('action_required')}<br/>
                    <strong>Assigned To:</strong> <span style="color: #0055a4; font-weight: bold;">{assigned_text}</span><br/>
                    <strong>Escalation Contact:</strong> ⚠️ {t.get('escalation_contact', 'N/A')}</p>
                </div>
                """, unsafe_allow_html=True)
                
                btn_cols = st.columns(2)
                with btn_cols[0]:
                    if st.button(f"✅ Mark Resolved", key=f"res_{t['id']}"):
                        db_service.resolve_ticket(t['id'], logged_in_user["name"])
                        st.cache_data.clear() # Clear cache to instantly refresh Roster
                        st.rerun()
                with btn_cols[1]:
                    if t.get("status") == "Open":
                        if st.button(f"🚨 Escalate", key=f"esc_{t['id']}", type="primary"):
                            db_service.escalate_ticket(t['id'], logged_in_user["name"])
                            st.cache_data.clear() # Clear cache to show Manager as Busy
                            st.rerun()

                # Activity Log & Comments (Open)
                with st.expander("📝 Activity Log & Comments"):
                    activities = t.get("activity_log", [])
                    if activities:
                        for act in activities:
                            st.caption(f"**{act['user']}** - {act['action']} ({act['timestamp'][:16].replace('T', ' ')})")
                            if act.get('comment'):
                                st.write(f"*{act['comment']}*")
                    else:
                        st.caption("No activity yet.")
                        
                    new_comment = st.text_input("Add a comment", key=f"comment_input_open_{t['id']}")
                    if st.button("Post Comment", key=f"post_comment_open_{t['id']}"):
                        if new_comment:
                            db_service.add_ticket_activity(t['id'], logged_in_user['name'], "Comment", new_comment)
                            st.rerun()

                # Reassign Logic (Managers & Admins)
                if is_admin or is_manager:
                    with st.expander("🔄 Reassign Ticket"):
                        all_users = get_all_users_cached()
                        # Filter for available users
                        if is_admin:
                            available_users = [u for u in all_users if u.get("status") == "Available"]
                        else:
                            available_users = [u for u in all_users if u.get("status") == "Available" and u.get("reporting_to") == logged_in_user["name"]]
                        
                        if available_users:
                            user_options = {f"{u['name']} ({u['role']}) - {u.get('building_assigned')}": u for u in available_users}
                            selected_user_label = st.selectbox("Select Employee to Reassign", options=list(user_options.keys()), key=f"reassign_sel_{t['id']}")
                            if st.button("Reassign", key=f"reassign_btn_{t['id']}", type="primary"):
                                new_employee = user_options[selected_user_label]
                                db_service.reassign_ticket(t['id'], new_employee, logged_in_user["name"])
                                st.rerun()
                        else:
                            st.warning("No available employees to reassign to.")

        with resolved_col:
            st.markdown(f"### 🟢 Resolved ({len(resolved_tickets)})")
            for t in resolved_tickets:
                severity = t.get("severity", "Low")
                assigned = t.get("assigned_employee")
                assigned_text = "Unassigned"
                if assigned:
                    assigned_text = f"{assigned.get('name')} ({assigned.get('role')})"
                
                st.markdown(f"""
                <div class="ticket-card status-Resolved">
                    <h4><del>{t.get('id')} - {t.get('incident_type')}</del></h4>
                    <p style="color: #6c757d;">
                    <em>Resolved at {t.get('resolved_at', 'unknown time')}</em><br/>
                    <strong>Location:</strong> {t.get('location')}<br/>
                    <strong>Escalation Contact:</strong> {t.get('escalation_contact', 'N/A')}<br/>
                    <strong>Handled By:</strong> {assigned_text}</p>
                </div>
                """, unsafe_allow_html=True)
                
                # Activity Log & Comments (Resolved)
                with st.expander("📝 Activity Log & Comments"):
                    activities = t.get("activity_log", [])
                    if activities:
                        for act in activities:
                            st.caption(f"**{act['user']}** - {act['action']} ({act['timestamp'][:16].replace('T', ' ')})")
                            if act.get('comment'):
                                st.write(f"*{act['comment']}*")
                    else:
                        st.caption("No activity yet.")
                        
                    new_comment = st.text_input("Add a comment", key=f"comment_input_res_{t['id']}")
                    if st.button("Post Comment", key=f"post_comment_res_{t['id']}"):
                        if new_comment:
                            db_service.add_ticket_activity(t['id'], logged_in_user['name'], "Comment", new_comment)
                            st.rerun()

                if is_admin or is_manager:
                    with st.expander("🔄 Reopen Ticket"):
                        st.info("Reopening a ticket will move it back to the Open queue and mark the assigned employee as Occupied.")
                        if st.button("Reopen", key=f"reopen_btn_{t['id']}", type="primary"):
                            db_service.reopen_ticket(t['id'], logged_in_user["name"])
                            st.cache_data.clear()
                            st.rerun()

# --- TAB 2: COPILOT CHAT ---
with tab2:
    st.subheader("Operational Copilot")
    st.write("Report an incident for automatic triage, or ask questions about current stadium operations.")
    
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {"role": "model", "content": "Hello! I am your VenueOps Copilot. You can report an incident (e.g., 'Spill at Gate B') and I will automatically triage it and create a ticket. Or you can ask me questions about operations."}
        ]

    # Display chat messages
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Chat input
    if prompt := st.chat_input("Type your report or query here..."):
        # Add user message to state
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("model"):
            with st.spinner("Analyzing..."):
                # Simple heuristic to determine if it's a report or a general question
                # In a real app, you might use an LLM classifier first.
                if any(word in prompt.lower() for word in ["report", "spill", "fight", "crowd", "emergency", "broken", "issue", "water", "leak", "plumbing", "medical", "help", "not working", "fire", "smoke", "missing", "lost", "clean", "dirty", "trash", "toilet", "repair"]):
                    # Triage workflow
                    st.write("🔍 *Analyzing incident report...*")
                    triage_result = triage_incident(prompt)
                    
                    if "error" in triage_result:
                        response_text = f"❌ **Error during triage:** {triage_result['error']}"
                        st.error(response_text)
                    else:
                        st.write("⏳ *Generating structured ticket...*")
                        
                        # Duplicate Ticket Prevention

                        all_tickets = get_all_tickets_cached()
                        is_duplicate = False
                        for t in all_tickets:
                            if t.get("status") == "Open" and t.get("location") == triage_result.get("location") and t.get("incident_type") == triage_result.get("incident_type"):
                                is_duplicate = True
                                break
                                
                        if is_duplicate:
                            response_text = f"⚠️ **Duplicate Incident Detected:** A ticket for '{triage_result.get('incident_type')}' at '{triage_result.get('location')}' already exists and is currently Open."
                            st.warning(response_text)
                        else:
                            ticket_id = db_service.create_ticket(triage_result)
                            
                            if ticket_id:
                                response_text = f"✅ **Incident Triaged and Logged successfully as {ticket_id}.**\n\n"
                                response_text += f"**Category:** {triage_result.get('incident_type')}\n"
                                response_text += f"**Severity:** {triage_result.get('severity')}\n"
                                response_text += f"**Action Dispatched:** {triage_result.get('action_required')}"
                                st.success("Ticket added to Incident Board.")
                            else:
                                response_text = "❌ Failed to save ticket to database."
                                st.error(response_text)
                else:
                    # General chat workflow
                    response_text = chat_with_copilot(st.session_state.messages, prompt)
                
                st.markdown(response_text)
                st.session_state.messages.append({"role": "model", "content": response_text})

# --- TAB 3: WORKFORCE ROSTER ---
with tab3:
    st.subheader("👥 Live Workforce Roster")
    st.write("Real-time view of employee availability and location assignment. Data is combined from `employee_details` and `employee_availability`.")
    if st.button("🔄 Refresh Roster"):
        st.rerun()
        

    all_users = get_all_users_cached()
    if is_admin:
        roster = all_users
    elif is_manager:
        roster = [u for u in all_users if u.get("reporting_to") == logged_in_user["name"]]
    else:
        # Employees don't usually see roster, but if they do, maybe just themselves
        roster = [u for u in all_users if u.get("id") == logged_in_user["id"]]
    
    if roster:
        df = pd.DataFrame(roster)
        # Reorder and rename columns for display
        df = df[["id", "name", "role", "status", "building_assigned", "floor_assigned", "contact", "reporting_to"]]
        df.columns = ["ID", "Name", "Role", "Status", "Building", "Floor", "Contact", "Manager"]
        
        # --- Filters ---
        st.markdown("##### Filter Employees")
        f_col1, f_col2, f_col3, f_col4 = st.columns(4)
        
        search_query = f_col1.text_input("🔍 Search Name/ID")
        role_filter = f_col2.selectbox("Role", ["All"] + sorted(df["Role"].unique().tolist()))
        status_filter = f_col3.selectbox("Status", ["All", "Available", "Occupied"])
        
        # Prevent double 'All' if 'All' is already in the unique buildings
        # Filter out None values before sorting to avoid TypeError
        buildings_list = [str(b) for b in df["Building"].unique().tolist() if b is not None]
        buildings_list = [b for b in sorted(buildings_list) if b != "All"]
        bldg_filter = f_col4.selectbox("Building", ["All"] + buildings_list)
        
        # Apply Filters
        if search_query:
            df = df[df["Name"].str.contains(search_query, case=False, na=False) | df["ID"].str.contains(search_query, case=False, na=False)]
        if role_filter != "All":
            df = df[df["Role"] == role_filter]
        if status_filter != "All":
            df = df[df["Status"] == status_filter]
        if bldg_filter != "All":
            df = df[df["Building"] == bldg_filter]
            
        st.caption(f"Showing {len(df)} employee(s)")
        
        # Apply color coding to status
        def color_status(val):
            if val == 'Available': return 'color: #28a745; font-weight: bold;'
            elif val == 'Occupied': return 'color: #dc3545; font-weight: bold;'
            return ''
            
        styled_df = df.style.map(color_status, subset=['Status'])
        st.dataframe(styled_df, use_container_width=True, hide_index=True)
    else:
        st.info("No employee data found.")

# --- TAB 4: SETTINGS (ADMIN ONLY) ---
# --- TAB 4: SETTINGS ---
with tab4:
    st.subheader("⚙️ Settings & User Management")
    st.write("Add or remove users from the workforce database.")
    
    col_form, col_list = st.columns([1, 2])
    
    with col_form:
        st.markdown("#### Edit My Profile")
        with st.form("edit_my_profile"):
            new_phone = st.text_input("Update Phone Number", value=logged_in_user.get("phone_number", ""))
            new_addr = st.text_input("Update Address", value=logged_in_user.get("address", ""))
            new_pass = st.text_input("Update Password", type="password", placeholder="Leave blank to keep current")
            
            if st.form_submit_button("Save Profile", type="primary"):
                updates = {"phone_number": new_phone, "address": new_addr}
                if new_pass:
                    updates["password"] = new_pass
                db_service.update_user(logged_in_user["id"], updates)
                st.success("Profile updated! Please log in again to reflect changes.")
                
        st.markdown("---")
        if is_admin:
            st.markdown("#### Add New User")
            with st.form("add_user_form"):
                new_name = st.text_input("Full Name")
                
                allowed_roles = ["Security", "Cleaner", "Medic", "Technician"]
                if is_admin:
                    allowed_roles = ["Admin", "Manager"] + allowed_roles
                elif is_manager:
                    allowed_roles = ["Manager"] + allowed_roles
                    
                new_role = st.selectbox("Role", allowed_roles)
                new_manager = st.text_input("Reporting To (Manager Name)")
                new_phone = st.text_input("Phone Number")
                new_address = st.text_input("Address")
                new_password = st.text_input("Password", value="password123", type="password")
                
                submitted = st.form_submit_button("Add User", type="primary")
                if submitted:
                    if new_name and new_password:
                        # Auto-generate a standardized sequential ID (e.g. EMP042)
                        all_users = get_all_users_cached()
                        existing_ids = [int(u["id"][3:]) for u in all_users if u["id"].upper().startswith("EMP") and u["id"][3:].isdigit()]
                        next_num = max(existing_ids) + 1 if existing_ids else 1
                        generated_id = f"EMP{next_num:03d}"
                        
                        user_data = {
                            "id": generated_id,
                            "name": new_name,
                            "role": new_role,
                            "reporting_to": new_manager,
                            "phone_number": new_phone,
                            "contact": new_phone,  # Sync both fields for legacy compatibility
                            "address": new_address,
                            "password": new_password,
                            "status": "Available",
                            "building_assigned": "All",
                            "floor_assigned": "All"
                        }
                        db_service.add_user(user_data)
                        st.success(f"Added {new_name} with ID {generated_id}!")
                        st.rerun()
                    else:
                        st.error("Name and Password are required.")
                    
    with col_list:
        st.markdown("#### Current Users")
        all_users = get_all_users_cached()
        
        visible_users = []
        if is_admin:
            visible_users = all_users
        elif is_manager:
            visible_users = [u for u in all_users if u.get("reporting_to") == logged_in_user["name"]]
        else:
            visible_users = [u for u in all_users if u.get("id") == logged_in_user["id"]]
            
        for u in visible_users:
            with st.expander(f"{u['name']} ({u['role']}) - {u['id']}"):
                st.write(f"**Phone:** {u.get('phone_number', 'N/A')}")
                st.write(f"**Address:** {u.get('address', 'N/A')}")
                st.write(f"**Manager:** {u.get('reporting_to', 'N/A')}")
                
                if is_admin or u['id'] == logged_in_user['id']:
                    with st.form(f"edit_{u['id']}"):
                        if is_admin:
                            st.write("Admin: Edit User")
                            all_roles = ["Admin", "Manager", "Security", "Cleaner", "Medic", "Technician"]
                            e_role = st.selectbox("Role", all_roles, index=all_roles.index(u.get("role")) if u.get("role") in all_roles else 0)
                            e_manager = st.text_input("Manager", value=u.get("reporting_to", ""))
                            e_building = st.text_input("Building", value=u.get("building_assigned", ""))
                            e_floor = st.text_input("Floor", value=u.get("floor_assigned", ""))
                        else:
                            st.write("Edit My Profile")
                            
                        e_phone = st.text_input("Phone Number", value=u.get("phone_number", ""))
                        e_addr = st.text_input("Address", value=u.get("address", ""))
                        e_pass = st.text_input("Reset Password", type="password", placeholder="Leave blank to keep current")
                        if st.form_submit_button("Save User"):
                            updates = {
                                "phone_number": e_phone, 
                                "address": e_addr
                            }
                            if is_admin:
                                updates.update({
                                    "role": e_role,
                                    "reporting_to": e_manager,
                                    "building_assigned": e_building,
                                    "floor_assigned": e_floor
                                })
                            if e_pass:
                                updates["password"] = e_pass
                            db_service.update_user(u["id"], updates)
                            st.success("User updated!")
                            st.rerun()
                            
                if is_admin:
                    if st.button("Delete User", key=f"del_{u['id']}"):
                        db_service.delete_user(u['id'])
                        st.rerun()
