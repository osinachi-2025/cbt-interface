# CBT Exam Workflow - Full Exam vs Practice Mode

## Overview
The exam system now allows students to choose between two modes after selecting a subject and session:
1. **Full Exam** - Take a complete exam covering all topics
2. **Practice Mode** - Select specific topics and practice with questions from those topics

## Workflow Diagram

```
Student logs in
    ↓
/cbt - Select Subject & Session
    ↓
Confirm Selection → Summary Modal
    ↓
REDIRECTS TO: /exam-mode-selection (NEW!)
    ├─ Full Exam Button
    │   └─ FULL EXAM FLOW (existing cbt_interface logic)
    └─ Practice Mode Button
        ↓
    /practice-mode (NEW!) - Select Topics
        ↓
    /practice-exam (NEW!) - Practice Exam Interface
        ↓
    Results Modal with Score & Feedback
```

## New Pages Created

### 1. exam_mode_selection.html
**Location:** `templates/exam_mode_selection.html`

After selecting a subject/session, students see two options:
- **Full Exam**: Take all questions from the selected subject for that session
- **Practice Mode**: Select specific topics and practice them

Features:
- Beautiful card-based UI with icons and feature lists
- Session info display (student name, subject, session)
- Back button to change subject/session selection

### 2. practice_mode.html
**Location:** `templates/practice_mode.html`

Students select which topics they want to practice:
- Shows all available topics for the selected subject
- Checkboxes to select/deselect individual topics
- "Select All" option for quick selection
- Selection counter showing how many topics are selected
- Start button (disabled until at least one topic is selected)

Features:
- Topic cards with descriptions
- Visual feedback for selected topics
- Error message if trying to start without selecting topics
- Back button to change exam mode

### 3. practice_exam.html
**Location:** `templates/practice_exam.html`

The actual practice exam interface:
- Displays questions from selected topics
- Multiple choice options with visual feedback
- **Instant feedback on answers** - shows if answer is correct/incorrect with explanation
- Navigation between questions
- Finish button to complete practice
- Results modal showing score and statistics

Features:
- Keyboard navigation (arrow keys)
- Progress tracking (current question / total)
- Immediate answer validation
- Beautiful glassmorphic design matching the system

## Backend Routes Added

### 1. `/exam-mode-selection` (GET)
Displays the exam mode selection page
- Parameters: `subject_id`, `session`
- Verifies subject and session exist before showing page

### 2. `/practice-mode` (GET)
Displays the practice mode topic selection page
- Parameters: `subject_id`, `session`
- Verifies subject and session exist before showing page

### 3. `/practice-exam` (GET)
Displays the practice exam interface
- Parameters: `subject_id`, `session`
- Questions are loaded via JavaScript from API endpoint

### 4. `/api/practice-questions/<subject_id>` (GET)
**New API Endpoint** - Returns questions for selected topics
- Parameters:
  - `topic_ids`: Comma-separated list of topic IDs
  - `session`: Session ID to filter by
- Returns: JSON array of question objects with:
  - `id`: Question ID
  - `question_text`: The question
  - `option_a`, `option_b`, `option_c`, `option_d`: Multiple choice options
  - `correct_answer`: The correct answer (A, B, C, or D)

## Modified Files

### 1. app.py
- Added 4 new routes for the workflow
- Added `/api/practice-questions/<subject_id>` endpoint
- All routes require `@login_required` decorator

### 2. templates/cbt_interface.html
- Modified the "Confirm & Start" button to redirect to `/exam-mode-selection` instead of loading exam questions
- Stores session display name in sessionStorage for use in other pages
- Maintains existing full exam functionality (when Full Exam is selected)

## How to Use

### For Students - Full Exam:
1. Go to `/cbt`
2. Select Subject & Session
3. Fill in student info and click "Start Exam"
4. Review and confirm
5. **New:** Choose "Full Exam" mode
6. Take the exam (existing interface)

### For Students - Practice Mode:
1. Go to `/cbt`
2. Select Subject & Session
3. Fill in student info and click "Start Exam"
4. Review and confirm
5. **New:** Choose "Practice Mode"
6. **New:** Select one or more topics
7. **New:** Take practice exam with instant feedback
8. View results and score

## Data Flow

### Session Storage Used:
- `studentName` - Student's name
- `selectedSubject` - Subject name
- `selectedSubjectId` - Subject ID
- `selectedSession` - Session ID
- `selectedSession_display` - Display name of session
- `examType` - Type of exam ('full' or 'practice')
- `practiceTopics` - JSON array of selected topic IDs

### API Calls:
1. `/api/get-topics/<subject_id>` - Get available topics (existing endpoint, updated)
2. `/api/practice-questions/<subject_id>` - Get questions for selected topics (new)

## Styling & Design

All new pages use the same modern glassmorphic design as the existing CBT interface:
- Purple gradient background
- Glass-effect cards with backdrop filtering
- Smooth animations and transitions
- Font: Inter font family
- Responsive design for mobile devices
- Accessibility features (focus states, high contrast mode support)

## Future Enhancements

Possible additions:
1. Save practice progress/bookmarks
2. Practice statistics (topics with most mistakes)
3. Timed practice mode
4. Difficulty levels for practice
5. Topic-based study recommendations
6. Practice attempt history
