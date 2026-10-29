import pandas as pd
import streamlit as st
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path

from src.lecturecraft_core import (
   build_default_tasks_for_lesson,
   ensure_demo_data,
   generate_activity_studio,
   generate_lesson_plan,
   load_all,
   parse_task_conflicts,
   save_all,
   search_records,
   validate_agenda_minutes,
)

st.set_page_config(page_title="LectureCraft AI", page_icon="🎓", layout="wide")

NAV_ITEMS = [
   "Dashboard",
   "Create Lesson",
   "My Lesson Plans",
   "Activity & Quiz Studio",
   "Teaching Calendar",
   "Workload Tasks",
   "Settings",
]


@st.cache_data(show_spinner=False)
def get_project_data():
   ensure_demo_data()
   return load_all()


def current_data():
   if "app_data" not in st.session_state:
       st.session_state.app_data = get_project_data()
   return st.session_state.app_data


def persist_data():
   data = st.session_state.app_data
   save_all(data["lessons"], data["sessions"], data["tasks"], data["settings"])


def slugify(value):
   return "".join(ch.lower() if ch.isalnum() else "-" for ch in value).strip("-") or "lesson"


def as_date(value):
   if not value:
       return datetime.today().date()
   try:
       return datetime.strptime(value, "%Y-%m-%d").date()
   except ValueError:
       return datetime.today().date()


def get_upcoming_deadlines(tasks):
   today = datetime.today().date()
   upcoming = []
   for task in tasks:
       if task.get("status") == "completed":
           continue
       deadline = task.get("deadline")
       if deadline:
           try:
               due = datetime.strptime(deadline, "%Y-%m-%d").date()
           except ValueError:
               continue
           upcoming.append((due, task))
   return sorted(upcoming, key=lambda item: item[0])[:5]


def build_theme_css(theme_name):
   if theme_name == "dark":
       background = "#0b1220"
       panel = "#111b2d"
       card = "#162339"
       text = "#edf1ff"
       muted = "#b8c2de"
       border = "rgba(166, 180, 255, 0.18)"
       accent = "#7c8cff"
       accent_soft = "#1b2341"
       badge = "#1a2a50"
   else:
       background = "#f6f8ff"
       panel = "#ffffff"
       card = "#fdfdff"
       text = "#101a34"
       muted = "#4f5d7a"
       border = "rgba(72, 89, 135, 0.14)"
       accent = "#4f46e5"
       accent_soft = "#eef0ff"
       badge = "#eef2ff"

   return f"""
   <style>
   [data-testid="stAppViewContainer"] {{
       background: {background};
       color: {text};
   }}
   .stApp .block-container {{
       padding-top: 1rem;
   }}
   .lec-shell {{
       background: {panel};
       border: 1px solid {border};
       border-radius: 18px;
       box-shadow: 0 10px 25px rgba(15, 23, 42, 0.04);
       padding: 1rem 1.1rem;
   }}
   .lec-card {{
       background: {card};
       border: 1px solid {border};
       border-radius: 16px;
       padding: 1rem;
       margin-bottom: 1rem;
   }}
   .lec-pill {{
       display: inline-block;
       background: {accent_soft};
       color: {accent};
       border: 1px solid {border};
       border-radius: 999px;
       padding: 0.35rem 0.7rem;
       font-size: 0.75rem;
       font-weight: 700;
       margin-right: 0.35rem;
   }}
   .lec-header {{
       display: flex; justify-content: space-between; align-items: center; gap: 0.75rem;
       margin-bottom: 1rem;
   }}
   .lec-muted {{
       color: {muted};
   }}
   .lec-task-conflict {{
       border-left: 4px solid #f59e0b; background: rgba(245, 158, 11, 0.08); padding: 0.7rem; border-radius: 10px;
   }}
   .lec-editor-section {{
       background: {card}; border: 1px solid {border}; border-radius: 14px; padding: 0.9rem; margin-bottom: 0.9rem;
   }}
   .stDataFrame, .stTable {{
       background: {panel};
   }}
   </style>
   """


def compute_dashboard_metrics(data):
   lessons = data["lessons"]
   sessions = data["sessions"]
   tasks = data["tasks"]
   today = datetime.today().date()
   next_week = today + timedelta(days=7)

   scheduled_this_week = sum(
       1 for session in sessions if session.get("kind") == "teaching" and as_date(session.get("date")) >= today and as_date(session.get("date")) <= next_week
   )
   remaining_tasks = sum(1 for task in tasks if task.get("status") != "completed")
   upcoming_sessions = [
       session
       for session in sessions
       if session.get("kind") == "teaching" and as_date(session.get("date")) >= today
   ]
   recent_lessons = sorted(lessons, key=lambda lesson: lesson.get("last_edited", ""), reverse=True)[:4]
   deadline_items = get_upcoming_deadlines(tasks)
   return {
       "total_lessons": len(lessons),
       "scheduled_this_week": scheduled_this_week,
       "remaining_tasks": remaining_tasks,
       "upcoming_sessions": upcoming_sessions,
       "recent_lessons": recent_lessons,
       "deadline_items": deadline_items,
   }


def create_quick_lesson_form():
   data = current_data()
   settings = data["settings"]
   with st.form("lesson_form"):
       st.subheader("Lesson details")
       col1, col2 = st.columns(2)
       with col1:
           title = st.text_input("Lesson title or topic", value="Sustainable Cities and Climate Policy")
           subject = st.text_input("Subject or course", value="Environmental Studies")
           discipline = st.text_input("Academic discipline", value="Sustainability")
           student_level = st.selectbox(
               "Student level",
               ["beginner", "intermediate", "advanced", "undergraduate", "postgraduate", "custom"],
               index=3,
           )
           age_group = st.text_input("Age group or prior knowledge", value="19-24, introductory policy analysis")
       with col2:
           duration = st.number_input("Class duration (minutes)", min_value=30, max_value=180, value=90, step=10)
           teaching_format = st.selectbox("Teaching format", ["lecture", "seminar", "workshop", "lab", "tutorial", "online session"], index=0)
           class_size = st.number_input("Class size", min_value=8, max_value=500, value=36, step=1)
           teaching_style = st.selectbox("Teaching style", ["interactive", "discussion-based", "project-based", "demonstration", "balanced"], index=4)
           difficulty = st.selectbox("Difficulty level", ["introductory", "intermediate", "advanced"], index=1)

       st.subheader("Learning objectives")
       objectives_value = st.text_area(
           "Objectives (one per line)",
           value="Define the policy tools used to reduce urban emissions\nCompare policy strengths and trade-offs\nApply a sustainability framework to a city case study",
           help="Add measurable objectives that match the selected student level.",
       )
       learning_outcomes = st.text_area("Expected learning outcomes", value="Students will compare policy instruments, explain urban sustainability trade-offs, and apply systems thinking to climate resilience decisions.")

       st.subheader("Teaching preferences")
       materials = st.text_area("Available materials and classroom resources", value="Slide deck, policy comparison brief, case study sheet, whiteboard, projector")
       accessibility = st.text_area("Accessibility considerations", value="Offer printed summaries, allow discussion prompts in pairs, and provide captioned visuals for all slides.")
       notes = st.text_area("Syllabus notes or teacher-provided content", value="Use local case examples and keep the emphasis on policy trade-offs rather than abstract theory.")
       constraints = st.text_area("Constraints or required topics", value="Highlight how policy decisions affect equity and urban resilience.")

       submitted = st.form_submit_button("Generate Lesson Plan", type="primary")
       if submitted:
           form_data = {
               "title": title,
               "subject": subject,
               "discipline": discipline,
               "student_level": student_level,
               "age_group": age_group,
               "duration": int(duration),
               "format": teaching_format,
               "class_size": int(class_size),
               "teaching_style": teaching_style,
               "difficulty": difficulty,
               "learning_outcomes": learning_outcomes,
               "objectives": [line.strip() for line in objectives_value.splitlines() if line.strip()],
               "materials": [line.strip() for line in materials.splitlines() if line.strip()],
               "accessibility": accessibility,
               "teacher_notes": notes,
               "constraints": constraints,
               "prerequisites": [
                   "Basic familiarity with the topic area.",
                   "A short recap at the start supports students who need a quick refresher."
               ],
           }
           with st.spinner("Generating your lesson plan and validating the agenda timing..."):
               lesson = generate_lesson_plan(form_data)
           if "validation_warning" in lesson:
               st.warning(lesson["validation_warning"])
           st.session_state.generated_lesson = lesson
           st.session_state.selected_lesson_id = lesson["id"]
           st.session_state.current_page = "Create Lesson"
           return


def render_dashboard():
   data = current_data()
   metrics = compute_dashboard_metrics(data)
   settings = data["settings"]
   st.markdown(f"<div class='lec-shell'><div class='lec-header'><div><h2 style='margin:0'>Good afternoon, {settings.get('name', 'Dr. Maya Chen')}</h2><div class='lec-muted'>{datetime.now().strftime('%A, %B %d, %Y')}</div></div><div><span class='lec-pill'>Demo mode</span><span class='lec-pill'>Faculty workspace</span></div></div></div>", unsafe_allow_html=True)
   c1, c2, c3, c4 = st.columns(4)
   c1.metric("Total saved lessons", metrics["total_lessons"])
   c2.metric("Lessons scheduled this week", metrics["scheduled_this_week"])
   c3.metric("Preparation tasks remaining", metrics["remaining_tasks"])
   c4.metric("Upcoming teaching sessions", len(metrics["upcoming_sessions"]))

   st.subheader("Recent lesson plans")
   if metrics["recent_lessons"]:
       recent_cols = st.columns(4)
       for idx, lesson in enumerate(metrics["recent_lessons"]):
           with recent_cols[idx]:
               st.markdown(f"<div class='lec-card'><strong>{lesson.get('title')}</strong><br><span class='lec-muted'>{lesson.get('subject')}</span><br>Duration: {lesson.get('duration')} min<br>Edited: {lesson.get('last_edited', '')[:10]}</div>", unsafe_allow_html=True)
               if st.button("Open", key=f"open-dashboard-{lesson['id']}"):
                   st.session_state.selected_lesson_id = lesson["id"]
                   st.session_state.current_page = "My Lesson Plans"
   else:
       st.info("No saved lesson plans yet. Create your first lesson to get started.")

   st.subheader("Weekly preparation workload")
   chart_data = {"Monday": 5, "Tuesday": 4, "Wednesday": 6, "Thursday": 3, "Friday": 2}
   chart_df = pd.DataFrame({"Day": list(chart_data.keys()), "Prep hours": list(chart_data.values())})
   st.bar_chart(chart_df.set_index("Day"), x="Day")

   st.subheader("Upcoming deadlines")
   if metrics["deadline_items"]:
       for due, task in metrics["deadline_items"]:
           st.markdown(f"<div class='lec-card'><strong>{task['title']}</strong><br><span class='lec-muted'>Due {due.isoformat()} · {task.get('priority', 'Medium')}</span></div>", unsafe_allow_html=True)
   else:
       st.info("No important deadlines are currently due.")

   st.subheader("Quick actions")
   qc1, qc2, qc3 = st.columns(3)
   with qc1:
       if st.button("Create a lesson", type="primary"):
           st.session_state.current_page = "Create Lesson"
   with qc2:
       if st.button("Build a quiz"):
           st.session_state.current_page = "Activity & Quiz Studio"
   with qc3:
       if st.button("Plan preparation time"):
           st.session_state.current_page = "Workload Tasks"


def render_create_lesson():
   data = current_data()
   if "generated_lesson" in st.session_state:
       lesson = st.session_state.generated_lesson
       st.subheader("Generated lesson plan preview")
       if "validation_warning" in lesson:
           st.warning(lesson["validation_warning"])
       st.write(f"Subject: {lesson['subject']} · Level: {lesson['student_level']} · Duration: {lesson['duration']} minutes")
       st.write(lesson.get("learning_outcomes"))
       c1, c2 = st.columns(2)
       with c1:
           if st.button("Save generated lesson to library", type="primary"):
               lessons = data["lessons"]
               if not any(item["id"] == lesson["id"] for item in lessons):
                   lesson["status"] = "Ready"
                   lesson["last_edited"] = datetime.now().isoformat(timespec="seconds")
                   lessons.insert(0, lesson)
                   data["lessons"] = lessons
                   persist_data()
                   st.success("Lesson saved successfully.")
               else:
                   st.info("This lesson already exists in the library.")
       with c2:
           if st.button("Open lesson editor"):
               st.session_state.selected_lesson_id = lesson["id"]
               st.session_state.current_page = "My Lesson Plans"

       st.subheader("Agenda summary")
       for segment in lesson["agenda"]:
           st.markdown(f"- {segment['title']}: {segment['start']}-{segment['end']} min")

       st.subheader("Learning objectives")
       for objective in lesson["objectives"]:
           st.write(f"• {objective}")

   else:
       create_quick_lesson_form()


def render_lesson_editor(lesson):
   st.title(f"Editing: {lesson.get('title', 'Untitled Lesson')}")
   editor_copy = st.session_state.get("editor_copy")
   if editor_copy is None or editor_copy.get("id") != lesson["id"]:
       st.session_state.editor_copy = deepcopy(lesson)
       editor_copy = st.session_state.editor_copy

   lesson_buffer = st.session_state.editor_copy
   if lesson_buffer != lesson:
       st.warning("Unsaved changes are present.")

   main, side = st.columns([2, 1])
   with main:
       st.subheader("Lesson content")
       for index, section in enumerate(lesson_buffer.get("sections", [])):
           st.markdown(f"<div class='lec-editor-section'><h4>{index + 1}. {section.get('title', 'Untitled section')}</h4></div>", unsafe_allow_html=True)
           section["title"] = st.text_input("Section title", value=section.get("title", ""), key=f"edit-title-{lesson['id']}-{index}")
           section["content"] = st.text_area("Section content", value=section.get("content", ""), key=f"edit-content-{lesson['id']}-{index}", height=140)
           col_a, col_b, col_c = st.columns([1, 1, 1])
           with col_a:
               if st.button("Duplicate", key=f"dup-sec-{lesson['id']}-{index}"):
                   lesson_buffer["sections"].insert(index + 1, deepcopy(section))
                   st.rerun()
           with col_b:
               if st.button("Regenerate", key=f"regen-sec-{lesson['id']}-{index}"):
                   section["content"] = f"Updated {section.get('title', 'section')} notes based on the lesson topic: {lesson.get('title')}\n\n- Key idea\n- Example\n- Teacher reminder"
                   st.rerun()
           with col_c:
               if st.button("Remove", key=f"remove-sec-{lesson['id']}-{index}"):
                   lesson_buffer["sections"].pop(index)
                   st.rerun()
           st.write("---")

       if st.button("Add section"):
           lesson_buffer.setdefault("sections", [])
           lesson_buffer["sections"].append({
               "id": f"custom-{datetime.now().strftime('%H%M%S')}",
               "title": "New section",
               "type": "text",
               "content": "Add your section content here."
           })
           st.rerun()

   with side:
       st.subheader("Lesson outline")
       for segment in lesson_buffer.get("agenda", []):
           st.markdown(f"- {segment.get('title')} ({segment.get('duration')} min)")
       st.markdown("### Objectives")
       for objective in lesson_buffer.get("objectives", []):
           st.write(f"• {objective}")
       st.markdown("### Quick actions")
       if st.button("Save lesson"):
           lesson.update(deepcopy(lesson_buffer))
           lesson["last_edited"] = datetime.now().isoformat(timespec="seconds")
           for item in current_data()["lessons"]:
               if item["id"] == lesson["id"]:
                   item.update(deepcopy(lesson))
                   break
           persist_data()
           st.success("Lesson saved.")
       if st.button("Reset unsaved changes"):
           st.session_state.editor_copy = deepcopy(lesson)
           st.rerun()
       if st.button("Preview lesson"):
           st.session_state.preview_lesson = deepcopy(lesson)
       if st.button("Create student handout"):
           student_content = "\n\n".join(f"{section.get('title', '')}\n{section.get('content', '')}" for section in lesson_buffer.get("sections", []))
           st.download_button("Download student handout", data=student_content, file_name=f"{slugify(lesson.get('title'))}-handout.txt")
       if st.button("Download teacher version"):
           teacher_content = "\n\n".join(f"{section.get('title', '')}\n{section.get('content', '')}" for section in lesson_buffer.get("sections", [])) + "\n\nTeacher notes:\n" + str(lesson_buffer.get("teacher_notes", ""))
           st.download_button("Download teacher notes", data=teacher_content, file_name=f"{slugify(lesson.get('title'))}-teacher.txt")
       if st.button("Generate quiz"):
           st.session_state.current_page = "Activity & Quiz Studio"
           st.session_state.studio_topic = lesson.get("title")
       if st.button("Add preparation tasks"):
           tasks = current_data()["tasks"]
           existing_titles = {task["title"] for task in tasks if task.get("lesson_id") == lesson["id"]}
           for new_task in build_default_tasks_for_lesson(lesson):
               if new_task["title"] not in existing_titles:
                   tasks.append(new_task)
           current_data()["tasks"] = tasks
           persist_data()
           st.success("Preparation tasks were added.")


def render_lesson_library():
   data = current_data()
   lessons = data["lessons"]
   st.title("My Lesson Plans")
   search = st.text_input("Search by title, subject, or topic", key="library_search")
   filters = st.columns(4)
   with filters[0]:
       sort_option = st.selectbox("Sort by", ["Last updated", "Title", "Scheduled date"])
   with filters[1]:
       subject_filter = st.selectbox("Subject", ["All"] + sorted({lesson.get("subject", "") for lesson in lessons if lesson.get("subject")}), index=0)
   with filters[2]:
       level_filter = st.selectbox("Level", ["All"] + sorted({lesson.get("student_level", "") for lesson in lessons if lesson.get("student_level")}), index=0)
   with filters[3]:
       status_filter = st.selectbox("Status", ["All", "Draft", "Ready", "Scheduled"])

   if search:
       lessons = [lesson for lesson in lessons if search.lower() in lesson.get("title", "").lower() or search.lower() in lesson.get("subject", "").lower()]
   if subject_filter != "All":
       lessons = [lesson for lesson in lessons if lesson.get("subject") == subject_filter]
   if level_filter != "All":
       lessons = [lesson for lesson in lessons if lesson.get("student_level") == level_filter]
   if status_filter != "All":
       lessons = [lesson for lesson in lessons if lesson.get("status") == status_filter]

   if sort_option == "Title":
       lessons = sorted(lessons, key=lambda lesson: lesson.get("title", "").lower())
   elif sort_option == "Scheduled date":
       lessons = sorted(lessons, key=lambda lesson: lesson.get("scheduled_date", ""), reverse=True)
   else:
       lessons = sorted(lessons, key=lambda lesson: lesson.get("last_edited", ""), reverse=True)

   view_type = st.toggle("Grid view", value=True)
   if not lessons:
       st.info("No lessons match your filters. Create a lesson to begin.")
       if st.button("Create first lesson"):
           st.session_state.current_page = "Create Lesson"
       return

   if view_type:
       grid = st.columns(3)
       for idx, lesson in enumerate(lessons):
           with grid[idx % 3]:
               st.markdown(f"<div class='lec-card'><strong>{lesson.get('title')}</strong><br><span class='lec-muted'>{lesson.get('subject')} · {lesson.get('duration')} min</span><br><small>{lesson.get('student_level')} · {lesson.get('status')}</small></div>", unsafe_allow_html=True)
               if st.button("Open", key=f"lesson-open-{lesson['id']}"):
                   st.session_state.selected_lesson_id = lesson["id"]
                   st.session_state.current_page = "My Lesson Plans"
               action_cols = st.columns(4)
               with action_cols[0]:
                   if st.button("Edit", key=f"lesson-edit-{lesson['id']}"):
                       st.session_state.selected_lesson_id = lesson["id"]
                       st.session_state.editor_copy = deepcopy(lesson)
               with action_cols[1]:
                   if st.button("Duplicate", key=f"lesson-dup-{lesson['id']}"):
                       clone = deepcopy(lesson)
                       clone["id"] = f"lesson-{datetime.now().strftime('%H%M%S')}"
                       clone["title"] = f"{lesson.get('title')} (Copy)"
                       clone["status"] = "Draft"
                       data["lessons"].append(clone)
                       persist_data()
                       st.rerun()
               with action_cols[2]:
                   if st.button("Export", key=f"lesson-export-{lesson['id']}"):
                       payload = "\n\n".join(f"{section.get('title')}\n{section.get('content')}" for section in lesson.get("sections", []))
                       st.download_button("Download", data=payload, file_name=f"{slugify(lesson.get('title'))}.txt", key=f"download-{lesson['id']}")
               with action_cols[3]:
                   if st.button("Delete", key=f"lesson-del-{lesson['id']}"):
                       data["lessons"] = [item for item in data["lessons"] if item["id"] != lesson["id"]]
                       persist_data()
                       st.rerun()
   else:
       for lesson in lessons:
           row = st.columns([2, 1, 1, 1, 2])
           with row[0]:
               st.write(lesson.get("title"))
           with row[1]:
               st.write(lesson.get("subject"))
           with row[2]:
               st.write(lesson.get("duration"))
           with row[3]:
               st.write(lesson.get("status"))
           with row[4]:
               if st.button("Open", key=f"list-open-{lesson['id']}"):
                   st.session_state.selected_lesson_id = lesson["id"]
                   st.session_state.editor_copy = deepcopy(lesson)

   selected_id = st.session_state.get("selected_lesson_id")
   if selected_id:
       selected_lesson = next((lesson for lesson in data["lessons"] if lesson["id"] == selected_id), None)
       if selected_lesson:
           st.write("---")
           render_lesson_editor(selected_lesson)


def render_studio():
   data = current_data()
   st.title("Activity & Quiz Studio")
   topic = st.text_input("Topic or learning objective", value=st.session_state.get("studio_topic", "Sustainable Cities"))
   level = st.selectbox("Student level", ["beginner", "intermediate", "advanced", "undergraduate", "postgraduate"], index=1)
   activity_type = st.selectbox("Activity or assessment type", ["Discussion", "Critical thinking task", "Problem solving", "Reflection", "Case analysis"], index=2)
   quantity = st.slider("Number of activities or questions", 1, 5, 3)
   difficulty = st.selectbox("Difficulty", ["Foundational", "Developing", "Challenging"], index=1)
   duration = st.slider("Estimated completion time (minutes)", 10, 60, 25)

   if st.button("Generate activity set", type="primary"):
       with st.spinner("Generating activities and quiz items..."):
           generated = generate_activity_studio(topic, level, activity_type, quantity, difficulty, duration)
       st.session_state.generated_studio = generated

   if "generated_studio" in st.session_state:
       generated = st.session_state.generated_studio
       st.subheader("Generated activities")
       for activity in generated["activities"]:
           st.markdown(f"<div class='lec-card'><strong>{activity['name']}</strong><br>{activity['purpose']}<br><span class='lec-muted'>Format: {activity['format']} · Duration: {activity['duration']} min</span></div>", unsafe_allow_html=True)
       st.subheader("Quiz preview")
       for index, question in enumerate(generated["quiz"], start=1):
           st.write(f"{index}. {question['question']}")
           st.write(f"Answer: {question['answer']}")

       if st.button("Add to active lesson"):
           if data["lessons"]:
               lesson = data["lessons"][0]
               lesson.setdefault("activities", [])
               for activity in generated["activities"]:
                   lesson["activities"].append(activity)
               lesson.setdefault("exit_quiz", [])
               for question in generated["quiz"]:
                   lesson["exit_quiz"].append(question)
               lesson["last_edited"] = datetime.now().isoformat(timespec="seconds")
               persist_data()
               st.success(f"Added to {lesson['title']}.")
           else:
               st.info("Create a lesson before adding activity content.")


def render_calendar():
   data = current_data()
   st.title("Teaching Calendar")
   month = st.date_input("Month", datetime.today())
   month_start = month.replace(day=1)
   month_end = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
   days = [month_start + timedelta(days=i) for i in range((month_end - month_start).days + 1)]
   date_lookup = {day.strftime("%Y-%m-%d"): [] for day in days}
   for session in data["sessions"]:
       date_lookup.setdefault(session.get("date"), [])
       date_lookup[session.get("date")].append(session)

   for day in days:
       date_str = day.strftime("%Y-%m-%d")
       if date_str not in date_lookup:
           date_lookup[date_str] = []

   schedule_cols = st.columns(7)
   weekdays = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
   for col, weekday in zip(schedule_cols, weekdays):
       col.caption(weekday)

   for index, day in enumerate(days):
       row_index = index // 7
       # row structure is not needed for simple calendar display; just show as a series of cards
       pass

   st.subheader("Schedule a class or preparation deadline")
   with st.form("calendar_form"):
       col1, col2, col3 = st.columns(3)
       with col1:
           lesson_id = st.selectbox("Linked lesson plan", [lesson["id"] for lesson in data["lessons"]], index=0 if data["lessons"] else None)
       with col2:
           session_date = st.date_input("Date")
       with col3:
           session_time = st.time_input("Time")
       duration = st.number_input("Duration (minutes)", min_value=15, max_value=240, value=90)
       location = st.text_input("Location or delivery format", value="Room B208")
       kind = st.selectbox("Type", ["teaching", "preparation"], index=0)
       submitted = st.form_submit_button("Save session")
   if submitted:
       new_session = {
           "id": f"session-{datetime.now().strftime('%H%M%S')}",
           "title": "Scheduled teaching session" if kind == "teaching" else "Preparation deadline",
           "lesson_id": lesson_id,
           "date": session_date.strftime("%Y-%m-%d"),
           "time": session_time.strftime("%H:%M"),
           "duration": int(duration),
           "location": location,
           "format": "lecture" if kind == "teaching" else "prep",
           "kind": kind,
       }
       data["sessions"].append(new_session)
       persist_data()
       st.success("Session saved and added to the calendar.")

   st.subheader("Upcoming calendar items")
   for session in sorted(data["sessions"], key=lambda item: item.get("date", "")):
       st.write(f"{session.get('date')} {session.get('time')} · {session.get('title')} · {session.get('kind')}")


def render_tasks():
   data = current_data()
   tasks = data["tasks"]
   conflicts = parse_task_conflicts(tasks)
   if conflicts:
       st.warning("Workload conflicts detected: some tasks share the same deadline and scheduled time.")
       for conflict in conflicts:
           st.markdown(f"<div class='lec-task-conflict'><strong>Conflict:</strong> {conflict['first']} and {conflict['second']} overlap on {conflict['date']}</div>", unsafe_allow_html=True)

   st.title("Workload Tasks")
   for task in tasks:
       status = task.get("status", "pending")
       if status == "completed":
           state = "✅ Completed"
       elif status == "in_progress":
           state = "⏳ In progress"
       else:
           state = "🟡 Pending"
       st.markdown(f"<div class='lec-card'><strong>{task['title']}</strong><br>{task.get('description')}<br><span class='lec-muted'>{state} · {task.get('deadline')} · {task.get('priority')} priority</span></div>", unsafe_allow_html=True)
       cols = st.columns([1, 1, 1, 1])
       with cols[0]:
           if st.button("Mark done", key=f"mark-done-{task['id']}"):
               task["status"] = "completed"
               persist_data()
               st.rerun()
       with cols[1]:
           if st.button("In progress", key=f"mark-progress-{task['id']}"):
               task["status"] = "in_progress"
               persist_data()
               st.rerun()
       with cols[2]:
           if st.button("Pending", key=f"mark-pending-{task['id']}"):
               task["status"] = "pending"
               persist_data()
               st.rerun()
       with cols[3]:
           if st.button("Remove", key=f"remove-task-{task['id']}"):
               data["tasks"] = [item for item in tasks if item["id"] != task["id"]]
               persist_data()
               st.rerun()


def render_settings():
   data = current_data()
   settings = data["settings"]
   st.title("Settings")
   with st.form("settings_form"):
       name = st.text_input("Teacher name", value=settings.get("name", "Dr. Maya Chen"))
       role = st.text_input("Role", value=settings.get("role", "Senior Lecturer, Sustainability Studies"))
       theme = st.selectbox("Theme preference", ["light", "dark"], index=0 if settings.get("theme") == "light" else 1)
       demo_mode = st.checkbox("Demo mode enabled", value=settings.get("demo_mode", True))
       if st.form_submit_button("Save settings"):
           settings["name"] = name
           settings["role"] = role
           settings["theme"] = theme
           settings["demo_mode"] = demo_mode
           persist_data()
           st.success("Settings saved.")

   if st.button("Reset demo data"):
       demo_lessons = [
           generate_lesson_plan({
               "title": "Climate Policy and Sustainable Cities",
               "subject": "Environmental Studies",
               "discipline": "Sustainability",
               "student_level": "undergraduate",
               "age_group": "19-24",
               "duration": 90,
               "format": "lecture",
               "class_size": 36,
               "teaching_style": "balanced",
               "difficulty": "intermediate",
               "learning_outcomes": "Students will compare policy instruments, explain urban sustainability trade-offs, and apply systems thinking to city resilience case studies.",
               "objectives": [
                   "Define the key policy tools used to reduce urban carbon emissions.",
                   "Compare the strengths and limitations of regulatory, market, and community-led approaches.",
                   "Apply a sustainability framework to evaluate a city resilience proposal."
               ],
               "materials": ["Slide deck", "Case brief", "Worksheet"],
               "teacher_notes": "Check the local policy examples for factual accuracy before the lesson."
           })
       ]
       demo_lessons[0]["sections"] = [
           {"id": "overview", "title": "Lesson overview", "type": "text", "content": "This lesson explores how cities use policy tools to reduce emissions while improving resilience and social equity."},
           {"id": "objectives", "title": "Learning objectives", "type": "text", "content": "- Define policy tools\n- Compare policy trade-offs\n- Evaluate a city resilience proposal"},
           {"id": "agenda", "title": "Timed agenda", "type": "text", "content": "- Introduction 0-12\n- Policy toolbox 12-32\n- Case work 32-52\n- Discussion 72-82\n- Exit quiz 82-90"},
       ]
       demo_lessons[0]["status"] = "Ready"
       data["lessons"] = demo_lessons
       data["sessions"] = [
           {
               "id": "session-demo-1",
               "title": "Urban Climate Policy Seminar",
               "lesson_id": demo_lessons[0]["id"],
               "date": (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d"),
               "time": "10:00",
               "duration": 90,
               "location": "Room B208",
               "format": "lecture",
               "kind": "teaching",
           }
       ]
       data["tasks"] = [
           {
               "id": "task-demo-1",
               "title": "Review syllabus and learning objectives",
               "description": "Double-check the lesson outcomes and learning objective wording.",
               "lesson_id": demo_lessons[0]["id"],
               "category": "Teaching Preparation",
               "estimated_duration": 25,
               "priority": "High",
               "deadline": (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"),
               "status": "in_progress",
               "scheduled_time": "09:00",
           },
           {
               "id": "task-demo-2",
               "title": "Prepare slides and examples",
               "description": "Prepare the slide deck and worked policy examples for the session.",
               "lesson_id": demo_lessons[0]["id"],
               "category": "Teaching Preparation",
               "estimated_duration": 45,
               "priority": "High",
               "deadline": (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d"),
               "status": "pending",
               "scheduled_time": "14:00",
           }
       ]
       persist_data()
       st.success("Demo data reset.")


def main():
   data = current_data()
   settings = data["settings"]
   st.markdown(build_theme_css(settings.get("theme", "light")), unsafe_allow_html=True)

   with st.sidebar:
       st.title("LectureCraft AI")
       st.caption("Plan smarter. Teach better.")
       current_page = st.session_state.get("current_page", "Dashboard")
       page = st.radio("Navigation", NAV_ITEMS, index=NAV_ITEMS.index(current_page), key="current_page")

       st.markdown("---")
       st.caption("Global search")
       search_term = st.text_input("Search saved lessons and tasks", key="global_search_input")
       if search_term:
           matches_l, matches_t = search_records(search_term, data["lessons"], data["tasks"])
           if matches_l or matches_t:
               st.write("Lesson matches:")
               for lesson in matches_l:
                   st.write(f"• {lesson['title']}")
               st.write("Task matches:")
               for task in matches_t:
                   st.write(f"• {task['title']}")
           else:
               st.write("No matches found.")

       if st.button("Quick create"):
           st.session_state.current_page = "Create Lesson"

       st.markdown("---")
       st.write(f"{settings.get('name', 'Dr. Maya Chen')} · {settings.get('role', 'Senior Lecturer')}")
       st.button("Notifications", disabled=True)

   st.markdown("<div class='lec-shell'><div class='lec-header'><div><h3 style='margin:0'>LectureCraft AI</h3><div class='lec-muted'>Demo-generated lesson planning workspace</div></div><div><span class='lec-pill'>Local demo</span><span class='lec-pill'>No secret keys</span></div></div></div>", unsafe_allow_html=True)

   if page == "Dashboard":
       render_dashboard()
   elif page == "Create Lesson":
       render_create_lesson()
   elif page == "My Lesson Plans":
       render_lesson_library()
   elif page == "Activity & Quiz Studio":
       render_studio()
   elif page == "Teaching Calendar":
       render_calendar()
   elif page == "Workload Tasks":
       render_tasks()
   elif page == "Settings":
       render_settings()


if __name__ == "__main__":
   main()
