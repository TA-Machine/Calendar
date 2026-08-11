# --- Drag & Drop Email Ingestion (Native Parsing - No Extra Dependencies) ---
with st.expander("📥 Drag & Drop New Bid Invitation (.eml or text)", expanded=False):
  uploaded_file = st.file_uploader("Upload Email File", type=["eml", "txt"])
  
  raw_text = ""
  if uploaded_file is not None:
    if uploaded_file.name.endswith(".eml"):
      msg = email.message_from_bytes(uploaded_file.read(), policy=policy.default)
      # Extract plain text body safely
      if msg.is_multipart():
        for part in msg.walk():
          if part.get_content_type() == "text/plain":
            raw_text = part.get_content()
            break
      else:
        raw_text = msg.get_content()
    else:
      raw_text = uploaded_file.getvalue().decode("utf-8", errors="ignore")

  # Fallback text area if they prefer copying and pasting email text directly
  manual_paste = st.text_area("Or paste email body text here:", value=raw_text, height=100)

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