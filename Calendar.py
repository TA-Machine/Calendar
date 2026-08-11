import datetime
import json
import os
import sqlite3
import urllib.request
import streamlit as st
import email
from email import policy

# --- Page Configuration ---
st.set_page_config(
    page_title="Roofing Bid Tracker", page_icon="🏗️", layout="wide"
)

# --- Database Setup ---
DB_FILE = "roofing_bids.db"


def init_db():
  conn = sqlite3.connect(DB_FILE)
  cursor = conn.cursor()
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_name TEXT,
            due_date TEXT,
            location TEXT,
            email TEXT,
            submission_link TEXT,
            roofing_system TEXT,
            insulation_thickness TEXT,
            membrane_type TEXT,
            attachment_type TEXT,
            metal_gauge TEXT,
            metal_color TEXT,
            metal_panels TEXT,
            dibs_status TEXT DEFAULT 'Unclaimed',
            dibs_color TEXT DEFAULT '#FFFFFF',
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
  conn.commit()
  conn.close()


init_db()

# --- Authentication Configuration ---
USERS = {"admin": "roofs2026", "joe": "joe123", "sarah": "sarah123"}


def check_login():
  if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.username = ""

  if not st.session_state.authenticated:
    st.markdown("## 🔒 Private Access Required")
    st.markdown(
        "Please enter your credentials to access the Roofing Bid Tracker."
    )
    with st.form("login_form"):
      username = st.text_input("Username")
      password = st.text_input("Password", type="password")
      submit = st.form_submit_button("Login")
      if submit:
        if username in USERS and USERS[username] == password:
          st.session_state.authenticated = True
          st.session_state.username = username
          st.rerun()
        else:
          st.error("Invalid username or password.")
    return False
  return True


if not check_login():
  st.stop()

# --- Gemini API Setup (Native REST - No External Library Required) ---
API_KEY = os.environ.get("GEMINI_API_KEY", "")


def parse_email_with_ai(email_text):
  if not API_KEY:
    return {
        "project_name": "New Project (API Key Missing)",
        "due_date": str(datetime.date.today() + datetime.timedelta(days=7)),
        "location": "Unknown",
        "email": "Unknown",
        "submission_link": "N/A",
        "roofing_system": "TPO / EPDM",
        "insulation_thickness": "2.5 inch",
        "membrane_type": "60 mil",
        "attachment_type": "Mechanically Attached",
        "metal_gauge": "24 Gauge",
        "metal_color": "Charcoal",
        "metal_panels": "Standard Drip Edge",
    }

  prompt = f"""
    Extract the following project details from this bid invitation email and return them strictly as a valid Python dictionary format with these exact keys:
    'project_name', 'due_date' (YYYY-MM-DD), 'location', 'email', 'submission_link', 'roofing_system', 'insulation_thickness', 'membrane_type', 'attachment_type', 'metal_gauge', 'metal_color', 'metal_panels'.
    
    Email Content:
    {email_text}
    """

  url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={API_KEY}"
  payload = {"contents": [{"parts": [{"text": prompt}]}]}

  req = urllib.request.Request(
      url,
      data=json.dumps(payload).encode("utf-8"),
      headers={"Content-Type": "application/json"},
      method="POST",
  )

  try:
    with urllib.request.urlopen(req) as response:
      res_data = json.loads(response.read().decode("utf-8"))
      response_text = res_data["candidates"][0]["content"]["parts"][0]["text"]

      import ast

      cleaned_text = (
          response_text.strip()
          .replace("```python", "")
          .replace("```json", "")
          .replace("```", "")
      )
      start_idx = cleaned_text.find("{")
      end_idx = cleaned_text.rfind("}") + 1
      return ast.literal_eval(cleaned_text[start_idx:end_idx])
  except Exception as e:
    return {
        "project_name": "Parsed Project (Error in AI parsing)",
        "due_date": str(datetime.date.today()),
        "location": "See notes",
        "email": "",
        "submission_link": "",
        "roofing_system": "",
        "insulation_thickness": "",
        "membrane_type": "",
        "attachment_type": "",
        "metal_gauge": "",
        "metal_color": "",
        "metal_panels": "",
    }


# --- Main Layout ---
st.title("🏗️ Roofing Bid Tracking Dashboard")
st.sidebar.write(f"Logged in as: **{st.session_state.username}**")

# --- Drag & Drop Email Ingestion ---
with st.expander("📥 Drag & Drop New Bid Invitation (.eml or text)", expanded=False):
  uploaded_file = st.file_uploader("Upload Email File", type=["eml", "txt"])

  raw_text = ""
  if uploaded_file is not None:
    if uploaded_file.name.endswith(".eml"):
      msg = email.message_from_bytes(uploaded_file.read(), policy=policy.default)
      if msg.is_multipart():
        for part in msg.walk():
          if part.get_content_type() == "text/plain":
            raw_text = part.get_content()
            break
      else:
        raw_text = msg.get_content()
    else:
      raw_text = uploaded_file.getvalue().decode("utf-8", errors="ignore")

  manual_paste = st.text_area(
      "Or paste email body text here:", value=raw_text, height=100
  )

  if st.button("Process Email with AI"):
    target_text = manual_paste if manual_paste else raw_text
    if not target_text.strip():
      st.warning("Please upload an email file or paste the email text first.")
    else:
      with st.spinner("Extracting project specifications..."):
        parsed_data = parse_email_with_ai(target_text)

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute(
            """
                INSERT INTO projects (project_name, due_date, location, email, submission_link, roofing_system, insulation_thickness, membrane_type, attachment_type, metal_gauge, metal_color, metal_panels, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                parsed_data.get("project_name", "Unknown Project"),
                parsed_data.get("due_date", str(datetime.date.today())),
                parsed_data.get("location", ""),
                parsed_data.get("email", ""),
                parsed_data.get("submission_link", ""),
                parsed_data.get("roofing_system", ""),
                parsed_data.get("insulation_thickness", ""),
                parsed_data.get("membrane_type", ""),
                parsed_data.get("attachment_type", ""),
                parsed_data.get("metal_gauge", ""),
                parsed_data.get("metal_color", ""),
                parsed_data.get("metal_panels", ""),
                "Initial email imported successfully.",
            ),
        )
        conn.commit()
        conn.close()
        st.success("Project successfully added to calendar!")
        st.rerun()

# --- Split Screen Layout: Calendar/List (Left) & Project Workspace (Right) ---
col_left, col_right = st.columns([1.2, 2])

with col_left:
  st.subheader("📅 Bid Calendar / Pipeline")

  conn = sqlite3.connect(DB_FILE)
  cursor = conn.cursor()
  cursor.execute(
      "SELECT id, project_name, due_date, dibs_status, dibs_color FROM projects"
      " ORDER BY due_date ASC"
  )
  projects = cursor.fetchall()
  conn.close()

  if not projects:
    st.info(
        "No projects found. Drag and drop an email above to create your first"
        " entry."
    )
    selected_project_id = None
  else:
    project_options = {
        f"{p[1]} (Due: {p[2]}) [Claimed: {p[3]}]": p[0] for p in projects
    }
    selected_label = st.selectbox(
        "Select Active Project", options=list(project_options.keys())
    )
    selected_project_id = project_options[selected_label]

    st.markdown("---")
    st.markdown("### Quick View Pipeline")
    for p in projects:
      color = p[4] if p[4] else "#ffffff"
      st.markdown(
          f"<div style='padding:8px; border-left: 6px solid"
          f" {color}; background-color: #262730; margin-bottom:5px;'>"
          f"<strong>{p[1]}</strong><br><small>Due: {p[2]} | Status:"
          f" {p[3]}</small></div>",
          unsafe_allow_html=True,
      )

with col_right:
  st.subheader("📝 Project Details & Team Workspace")

  if selected_project_id:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT project_name, due_date, location, email, submission_link,"
        " roofing_system, insulation_thickness, membrane_type, attachment_type,"
        " metal_gauge, metal_color, metal_panels, dibs_status, dibs_color, notes"
        " FROM projects WHERE id = ?",
        (selected_project_id,),
    )
    proj = cursor.fetchone()
    conn.close()

    if proj:
      (
          p_name,
          p_due,
          p_loc,
          p_email,
          p_link,
          p_roof,
          p_thick,
          p_memb,
          p_attach,
          p_mgauge,
          p_mcolor,
          p_mpanels,
          p_dibs,
          p_dcolor,
          p_notes,
      ) = proj

      # Team "Dibs" and Color Coding Section
      st.markdown("#### 🎨 Team Assignment ('Call Dibs')")
      dibs_col1, dibs_col2 = st.columns(2)
      with dibs_col1:
        new_dibs = st.text_input(
            "Claimed By / Status",
            value=p_dibs,
            key=f"dibs_{selected_project_id}",
        )
      with dibs_col2:
        new_color = st.color_picker(
            "Color Code",
            value=p_dicolor if p_dicolor else "#FF4B4B",
            key=f"color_{selected_project_id}",
        )

      # Editable Project Specifications (Top Bullet Points)
      st.markdown("#### 📌 Project Specifications (AI Generated / Editable)")
      with st.form(f"spec_form_{selected_project_id}"):
        col_s1, col_s2 = st.columns(2)
        with col_s1:
          edit_name = st.text_input("Project Name", value=p_name)
          edit_due = st.text_input("Due Date", value=p_due)
          edit_loc = st.text_input("Location", value=p_loc)
          edit_email = st.text_input("Contact Email", value=p_email)
          edit_link = st.text_input("Submission Link", value=p_link)
          edit_roof = st.text_input("Roofing System", value=p_roof)
        with col_s2:
          edit_thick = st.text_input(
              "Insulation Thickness", value=p_thick
          )
          edit_memb = st.text_input("Membrane Type", value=p_memb)
          edit_attach = st.text_input("Attachment Type", value=p_attach)
          edit_mgauge = st.text_input("Metal Gauge", value=p_mgauge)
          edit_mcolor = st.text_input("Metal Color", value=p_mcolor)
          edit_mpanels = st.text_input("Metal Panels Needed", value=p_mpanels)

        st.markdown("#### 💬 Co-worker Notes & Exchange")
        edit_notes = st.text_area("Discussion / Notes", value=p_notes, height=120)

        update_btn = st.form_submit_button("Save Changes")
        if update_btn:
          conn = sqlite3.connect(DB_FILE)
          cursor = conn.cursor()
          cursor.execute(
              """
                            UPDATE projects SET project_name=?, due_date=?, location=?, email=?, submission_link=?, roofing_system=?, insulation_thickness=?, membrane_type=?, attachment_type=?, metal_gauge=?, metal_color=?, metal_panels=?, dibs_status=?, dibs_color=?, notes=?
                            WHERE id=?
                        """,
              (
                  edit_name,
                  edit_due,
                  edit_loc,
                  edit_email,
                  edit_link,
                  edit_roof,
                  edit_thick,
                  edit_memb,
                  edit_attach,
                  edit_mgauge,
                  edit_mcolor,
                  edit_mpanels,
                  new_dibs,
                  new_color,
                  edit_notes,
                  selected_project_id,
              ),
          )
          conn.commit()
          conn.close()
          st.success("Changes saved successfully!")
          st.rerun()
  else:
    st.info("Select or create a project to view details.")