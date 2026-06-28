"""Role-aware mock RAG engine with a realistic institutional knowledge base."""

# ── Source document registry by role ─────────────────────────────────────────
_PUBLIC_SOURCES  = ["public_information_brochure.pdf", "campus_map_2025.pdf"]
_STUDENT_SOURCES = _PUBLIC_SOURCES + [
    "undergraduate_handbook_2024.pdf",
    "academic_calendar_2024_25.pdf",
    "student_code_of_conduct.pdf",
    "campus_facilities_guide.pdf",
]
_STAFF_SOURCES = _STUDENT_SOURCES + [
    "faculty_operational_procedures_v3.pdf",
    "internal_examination_guidelines.pdf",
    "administrative_circulars_Q1_2025.pdf",
    "research_grant_sop_2025.pdf",
]

SOURCES_BY_ROLE = {
    "Public":  _PUBLIC_SOURCES[:1],
    "Student": _STUDENT_SOURCES[:3],
    "Faculty": _STAFF_SOURCES[:5],
    "Admin":   _STAFF_SOURCES,
}

# ── Knowledge base: (keyword_string, {role: answer}) ─────────────────────────
# Keywords are pipe-separated; matched case-insensitively anywhere in the query.
KNOWLEDGE_BASE = [
    (
        "exam|test|examination|assessment|grade|grading|result|marks|cgpa|gpa|score|re-evaluation",
        {
            "Public": (
                "Examinations at our institution are conducted at the end of each academic semester. "
                "For detailed grading policies, exam schedules, and result information, please sign in "
                "with a student account or contact the office at exams@institution.edu."
            ),
            "Student": (
                "📚 **Examination & Grading Policy**\n\n"
                "**Schedule:** Mid-semester — Week 8 | End-semester — Week 16\n"
                "**Eligibility:** Minimum 75% attendance per subject to sit the exam.\n\n"
                "**Grading Scale:**\n"
                "• O (≥90%) — Outstanding  • A+ (≥80%) — Excellent\n"
                "• A (≥70%) — Very Good    • B+ (≥60%) — Good\n"
                "• B (≥50%) — Average      • C (≥40%) — Pass   • F (<40%) — Fail\n\n"
                "**Results:** Published within 21 working days on the student portal.\n"
                "**Re-evaluation:** Apply within 15 days of declaration (₹500 per subject).\n"
                "**Arrears:** Must be cleared within 2 consecutive attempts."
            ),
            "Faculty": (
                "📋 **Faculty Examination Guidelines (Internal SOP v3)**\n\n"
                "• Question paper submission to COE: 3 weeks before exam date (encrypted PDF + hard copy)\n"
                "• Internal marks (40% weightage): submit by Week 7 (mid-sem) and Week 14 (end-sem)\n"
                "• Mark entry deadline: 7 working days after exam via the faculty portal\n"
                "• Invigilation duties: allocated by COE 2 weeks prior\n"
                "• Grace marks: up to 3 per paper — requires HOD written approval\n"
                "• Malpractice incidents: report to Academic Integrity Committee within 48 hours\n"
                "• Script re-evaluation moderation: coordinated by the Exam Cell"
            ),
            "Admin": (
                "🔐 **Examination Administration (Admin Circular #2025-03)**\n\n"
                "• Hall tickets: auto-generated via ERP 10 days before exam; emailed to eligible students\n"
                "• Seating arrangement: COE uploads to portal 3 days before commencement\n"
                "• Answer script logistics: DHL courier SOP — dispatch within 24 hrs post-exam\n"
                "• Mark tabulation: auto-computed by ERP; manual overrides need Principal + COE sign-off\n"
                "• Results publishing: joint release by IT + COE after 48-hr staging review\n"
                "• Escalations: any irregularities → VC office within 2 business days\n"
                "• Full calendar: see Administrative Circulars Q1 2025"
            ),
        }
    ),
    (
        "scholarship|fee|financial aid|bursary|stipend|fund|loan|waiver|tuition|payment",
        {
            "Public": (
                "Our institution offers various scholarship and financial aid programmes. "
                "Specific eligibility criteria and application processes are available to enrolled students. "
                "For general enquiries, contact finance@institution.edu."
            ),
            "Student": (
                "💰 **Scholarships & Financial Aid**\n\n"
                "**Merit Scholarship:** Top 10% of each department — 50% tuition waiver.\n"
                "**Need-Based Aid:** Annual family income < ₹5L — up to 75% fee waiver; apply by Aug 31.\n"
                "**Sports Excellence Award:** National/state-level athletes — full tuition waiver.\n"
                "**SC/ST/OBC Scholarships:** Central & state government schemes — apply on NSP portal.\n\n"
                "**Fee Structure (2024-25):**\n"
                "• Tuition: ₹1,20,000/year  • Hostel: ₹48,000/year  • Misc: ₹12,000/year\n\n"
                "**Payment Deadlines:** Semester 1 — July 31 | Semester 2 — January 15\n"
                "Late fee: ₹100/day after the deadline. Apply via the student portal under Finance."
            ),
            "Faculty": (
                "💳 **Faculty Finance & Research Funding**\n\n"
                "• Research seed grants: up to ₹2L — apply through the Research Cell portal\n"
                "• Conference travel grants: ₹30,000/year for presenting at indexed conferences\n"
                "• AICTE/DST/SERB sponsored projects: institution provides 20% matching fund\n"
                "• Fee concession for faculty children: 50% on tuition — apply to HR\n"
                "• Salary advances: up to 3 months — Finance dept approval required\n"
                "Full procedures: Research Grant SOP 2025 (available on intranet)"
            ),
            "Admin": (
                "🏦 **Financial Administration (Admin Access)**\n\n"
                "• Fee collection: ERP auto-generates challan; reconciled daily with bank statement\n"
                "• Scholarship disbursement: processed by 15th of each month post-approval\n"
                "• Budget heads: refer to Financial Manual 2025 (Admin Circulars Q1 2025)\n"
                "• Vendor payments: three-way match (PO + receipt + invoice); Finance sign-off ≤ ₹1L, VC for >₹1L\n"
                "• Audit trail: all transactions logged in Tally with document reference\n"
                "• Endowment fund: managed by Finance Committee — quarterly statements to Board"
            ),
        }
    ),
    (
        "calendar|semester|schedule|academic year|holiday|break|vacation|session|timetable",
        {
            "Public": (
                "The academic year runs from July to April, divided into two semesters. "
                "For the detailed academic calendar, please visit the official website or sign in."
            ),
            "Student": (
                "📅 **Academic Calendar 2024-25**\n\n"
                "**Semester I (Odd):**\n"
                "• Commencement: July 15, 2024\n"
                "• Mid-semester exams: Sept 9–14, 2024\n"
                "• Diwali break: Oct 28 – Nov 3, 2024\n"
                "• End-semester exams: Nov 18 – Nov 30, 2024\n"
                "• Results: Dec 21, 2024\n\n"
                "**Semester II (Even):**\n"
                "• Commencement: January 6, 2025\n"
                "• Mid-semester exams: Feb 24 – Mar 1, 2025\n"
                "• End-semester exams: Apr 21 – May 3, 2025\n"
                "• Results: May 31, 2025\n\n"
                "**Public Holidays:** Jan 26, Aug 15, Gandhi Jayanti Oct 2, and 17 state/national holidays.\n"
                "Full calendar available on the student portal under Academics."
            ),
            "Faculty": (
                "📆 **Faculty Academic Timeline 2024-25**\n\n"
                "• Lesson plan submission: before Week 2 of each semester\n"
                "• Internal assessment 1: Week 5–6 | Internal assessment 2: Week 11–12\n"
                "• Course file submission: 2 weeks before end-semester exams\n"
                "• Board of Studies meeting: July & January (mandatory attendance)\n"
                "• Department audit: October & March\n"
                "• Annual faculty performance review: May\n"
                "Full faculty schedule: Faculty Operational Procedures v3, Appendix B"
            ),
            "Admin": (
                "🗓️ **Administrative Calendar (Admin Circulars Q1 2025)**\n\n"
                "• Admission cycle: March–June (TNEA/management quota)\n"
                "• Fee collection windows: July & January\n"
                "• NAAC/NBA compliance submissions: August & February\n"
                "• Governing Body meeting: June & December\n"
                "• Staff recruitment cycle: April–May\n"
                "• Annual report publication: June 30 each year\n"
                "• Infrastructure maintenance shutdown: May 5–25, 2025"
            ),
        }
    ),
    (
        "hostel|accommodation|dormitory|housing|room|mess|cafeteria|canteen|food|dining",
        {
            "Public": (
                "On-campus hostel accommodation is available for enrolled students. "
                "For room availability, fees, and application procedures, sign in to the student portal."
            ),
            "Student": (
                "🏠 **Hostel & Accommodation Guide**\n\n"
                "**Availability:** 4 blocks — Boys (A, B) and Girls (C, D); capacity 1,200 students.\n"
                "**Room Types:** Single (₹55,000/yr), Double-sharing (₹42,000/yr), Triple (₹35,000/yr)\n"
                "**Mess:** Vegetarian meals — Breakfast 7–9 AM | Lunch 12–2 PM | Dinner 7–9 PM\n"
                "**Monthly mess fee:** ₹3,500 (fixed) — optional for day scholars\n\n"
                "**Facilities:** Wi-Fi, laundry, 24/7 security, gym, recreation room\n"
                "**Curfew:** 10 PM (extendable for events with warden approval)\n"
                "**Application:** Hostel allotment portal opens April 15 — first come, first served\n"
                "**Grievances:** hostel.warden@institution.edu"
            ),
            "Faculty": (
                "🏘️ **Faculty Quarters & Guest House**\n\n"
                "• Faculty quarters: 48 units (2BHK) — allotted by seniority; apply to Estate Office\n"
                "• Guest house: 12 rooms — book via intranet portal (priority to visiting faculty)\n"
                "• Maintenance requests: raise ticket on the Facility Management portal\n"
                "• Mess for faculty: separate dining hall — subscription ₹2,800/month\n"
                "Full details: Faculty Operational Procedures v3, Section 6"
            ),
            "Admin": (
                "🏗️ **Hostel Administration (Admin Access)**\n\n"
                "• Capacity: 1,200 students (currently 1,080 occupied — 90% utilisation)\n"
                "• Allotment module: ERP Hostel Management; overrides need Estate Officer approval\n"
                "• Mess vendor contract: expires March 2026 — re-tender process to start October 2025\n"
                "• Security personnel: 24 guards in 3 shifts — duty roster in Admin Circular #2025-07\n"
                "• CCTV upgrade (64 cameras): sanctioned in Q1 2025 budget\n"
                "• Complaints dashboard: admin.hostel@institution.edu"
            ),
        }
    ),
    (
        "library|book|journal|resource|database|e-learning|lms|moodle|digital|online course",
        {
            "Public": (
                "Our institution maintains a well-equipped central library and digital learning resources. "
                "Enrolled students can access the online portal, e-journals, and digital library 24/7."
            ),
            "Student": (
                "📖 **Library & Learning Resources**\n\n"
                "**Central Library:** Mon–Sat 8 AM–10 PM | Sunday 10 AM–6 PM\n"
                "**Collection:** 45,000+ books, 12,000 e-books, 180 print journals\n\n"
                "**Digital Access (24/7):**\n"
                "• IEEE Xplore, Elsevier ScienceDirect, Springer Link\n"
                "• NPTEL / Coursera (institution-sponsored courses)\n"
                "• LMS (Moodle): lms.institution.edu — course materials, assignments, grades\n\n"
                "**Borrowing:** 4 books for 14 days | Fine: ₹2/day for late return\n"
                "**Inter-library Loan:** Request up to 3 external books/month\n"
                "**Study Rooms:** 6 bookable rooms (30 min slots) via library portal\n"
                "Contact: library@institution.edu | Ext. 2210"
            ),
            "Faculty": (
                "📚 **Faculty Library Privileges**\n\n"
                "• Borrowing: 10 books for 30 days (no fine for first 7 days overdue)\n"
                "• Journal procurement: submit request to Library Committee by December each year\n"
                "• Digital resources: additional Scopus + Web of Science access via faculty login\n"
                "• Course reserves: flag books for student priority; coordinate with librarian\n"
                "• Research databases: full Elsevier + Springer access + Turnitin for plagiarism\n"
                "• Book purchase budget: ₹50,000/dept/year — submit list to Library Committee"
            ),
            "Admin": (
                "🗄️ **Library Administration**\n\n"
                "• Annual budget: ₹18L (books: ₹8L, journals: ₹7L, digital: ₹3L)\n"
                "• RFID tracking: all assets tagged; annual stock verification in May\n"
                "• Koha LMS: system admin credentials in Admin Vault (IT)\n"
                "• Digital subscription renewals: Oct–Nov each year — Finance + Library sign-off\n"
                "• Accreditation: ISO 9001:2015 certified; NAAC documentation in Admin Circulars"
            ),
        }
    ),
    (
        "attendance|leave|absent|absence|late|bunk|proxy|shortage",
        {
            "Public": (
                "Attendance policies are applicable to all enrolled students. "
                "Please sign in for detailed information about attendance requirements and leave procedures."
            ),
            "Student": (
                "📊 **Attendance Policy**\n\n"
                "**Minimum Requirement:** 75% per subject per semester.\n"
                "**Shortage Warning:** Notification sent at 80% — check your portal regularly.\n"
                "**Condonation:** 65–74%: applies automatically if medical/official reason is submitted.\n"
                "**Below 65%:** Detained from writing the exam — no exceptions.\n\n"
                "**Leave Procedure:**\n"
                "1. Apply via student portal > Leave Request (minimum 1 day before)\n"
                "2. Medical leave: attach doctor's certificate within 3 days of return\n"
                "3. Long leave (>3 days): HOD approval required\n\n"
                "**View Attendance:** Student portal → Academics → Attendance Register\n"
                "⚠️ Proxy attendance is a disciplinary offence — results in suspension."
            ),
            "Faculty": (
                "📋 **Faculty Attendance & Leave Policy**\n\n"
                "• Casual Leave (CL): 12 days/year — apply 1 day prior on the portal\n"
                "• Earned Leave (EL): 30 days/year — encashable up to 15 days\n"
                "• Medical Leave (ML): 15 days with pay — medical certificate required\n"
                "• Duty Leave: for conferences/workshops — HOD + Principal approval\n"
                "• Compensatory Off: granted for weekend/holiday duty\n"
                "• Biometric attendance: mandatory daily; discrepancies → HR within 5 working days\n"
                "Full leave rules: Faculty Operational Procedures v3, Section 4"
            ),
            "Admin": (
                "🕐 **Attendance Administration**\n\n"
                "• Biometric data: synced with ERP every 30 minutes\n"
                "• Student attendance reports: generated daily at 5 PM; SMS sent to defaulters\n"
                "• Leave approval workflow: staff portal → Dept Head → HR → auto-salary deduction\n"
                "• Attendance audit: monthly by class coordinators\n"
                "• Mass absenteeism alerts: triggers HOD + Dean notification if >20% absent in a class\n"
                "• Payroll integration: LOP (Loss of Pay) computed from ERP on 25th of each month"
            ),
        }
    ),
    (
        "research|paper|publication|conference|phd|thesis|grant|project|patent",
        {
            "Public": (
                "Our institution has an active research ecosystem with numerous ongoing projects. "
                "For research collaboration or publication queries, contact research@institution.edu."
            ),
            "Student": (
                "🔬 **Student Research Opportunities**\n\n"
                "• **Undergraduate Research Program (URP):** Apply in Semester 3 — ₹5,000 stipend/month.\n"
                "• **Project funding:** IEDC grants up to ₹50,000 for innovative student projects.\n"
                "• **Paper publication:** Co-authorship with faculty — approach your advisor.\n"
                "• **Conference travel:** Institution funds ₹15,000 for paper presenters (indexed conferences).\n"
                "• **PhD admission:** Post-graduation — GATE score required; 10 seats per department.\n"
                "Contact: research.cell@institution.edu"
            ),
            "Faculty": (
                "🧪 **Research & Grants Guide (Research Grant SOP 2025)**\n\n"
                "• **Seed Research Grant:** Up to ₹2L internal — apply via Research Cell portal (rolling basis)\n"
                "• **SERB/DST/AICTE Proposals:** Institution provides 20% matching fund + overhead ₹1.5L\n"
                "• **Conference Travel:** ₹30,000/year for indexed conference papers\n"
                "• **Patent Filing:** Institution covers full cost; 50/50 revenue sharing\n"
                "• **Consultancy:** Faculty can take up to ₹5L/year; 70% to faculty, 30% to institution\n"
                "• **PhD Supervision:** Max 6 students per supervisor; progress reports every 6 months\n"
                "Full SOP: Research Grant SOP 2025 on intranet"
            ),
            "Admin": (
                "📊 **Research Administration**\n\n"
                "• Active funded projects: 28 (total corpus ₹4.2 Cr as of Q1 2025)\n"
                "• Grant utilisation: quarterly UC submission to funding agencies\n"
                "• IPR cell: 14 patents filed, 6 granted (2024-25)\n"
                "• Publication incentive: ₹10,000 for Scopus Q1/Q2, ₹5,000 for Scopus Q3/Q4\n"
                "• Research audit: annual by Internal Quality Assurance Cell (IQAC)\n"
                "• MOU with industry: 23 active MOUs — details in Research Circulars 2025"
            ),
        }
    ),
    (
        "circular|procedure|policy|sop|regulation|guideline|directive|notice",
        {
            "Public": (
                "Institutional policies and circulars are issued by the administration periodically. "
                "Public circulars are available on the official website. Sign in for internal SOPs."
            ),
            "Student": (
                "📢 **Recent Student Circulars & Policies**\n\n"
                "• **Circular #ST-2025-04:** Anti-ragging policy — zero tolerance; AICTE mandate.\n"
                "• **Circular #ST-2025-06:** Mobile phone policy — restricted in classrooms; Labs: banned.\n"
                "• **Circular #ST-2025-09:** Dress code — formal attire Mon–Wed, casuals Thu–Fri.\n"
                "• **Circular #ST-2025-11:** Placement registration open — register by Nov 30.\n\n"
                "All notices accessible on the Student Portal under 'Notifications'.\n"
                "For policy grievances: ombudsman@institution.edu"
            ),
            "Faculty": (
                "📌 **Faculty Circulars & SOPs (Q1 2025)**\n\n"
                "• **FC-2025-01:** NBA criterion documentation — update CVs in PBAS by March 15\n"
                "• **FC-2025-03:** R&D policy revision — new IP assignment clause effective April 1\n"
                "• **FC-2025-05:** Workload norms — 16 hrs/week teaching; remaining: research + admin\n"
                "• **FC-2025-07:** Digital content mandate — all courses must have LMS course page\n"
                "• **FC-2025-09:** Performance appraisal format updated — PBAS submission by May 31\n"
                "Full circular archive: Faculty Operational Procedures v3 + intranet portal"
            ),
            "Admin": (
                "🗂️ **Administrative Circulars & SOPs (Admin Circulars Q1 2025)**\n\n"
                "• **AC-2025-01:** ERP upgrade rollout plan — go-live April 15, 2025\n"
                "• **AC-2025-03:** Examination administration revised SOP\n"
                "• **AC-2025-05:** Procurement policy — GeM portal mandatory for orders >₹25,000\n"
                "• **AC-2025-07:** Security & hostel SOP revision\n"
                "• **AC-2025-09:** NAAC documentation — self-study report due by July 31, 2025\n"
                "• **AC-2025-11:** Anti-corruption compliance — mandatory training for all admin staff\n"
                "Full archive accessible in the Admin Document Repository"
            ),
        }
    ),
    (
        "admission|registration|enroll|application|form|document|certificate|transcript|transfer",
        {
            "Public": (
                "Admissions for the 2025-26 academic year are open. "
                "Visit our official website or contact admissions@institution.edu for details on programmes, "
                "eligibility, and the application process."
            ),
            "Student": (
                "📋 **Student Registration & Admissions**\n\n"
                "**Course Registration:** Each semester via the student portal (Week 1).\n"
                "**Add/Drop Period:** First 5 days of the semester only.\n"
                "**Required Documents (for new students):**\n"
                "• 10th & 12th mark sheets + certificates\n"
                "• Transfer Certificate from previous institution\n"
                "• Aadhar card + passport-size photos (6)\n"
                "• Category certificate (if applicable)\n\n"
                "**Transcripts:** Apply via portal → 7 working days processing → ₹200/copy\n"
                "**Bonafide Certificate:** Instant download from portal\n"
                "**Migration/TC:** Apply at least 30 days before requirement date"
            ),
            "Faculty": (
                "📝 **Faculty Appointment & Registration**\n\n"
                "• New faculty joining documents: verified by HR within 3 working days\n"
                "• ID card + portal access: provided by IT on Day 1\n"
                "• PF/ESI enrollment: HR initiates within 30 days of joining\n"
                "• Faculty profile update (PBAS): mandatory within first week of every academic year\n"
                "• Guest lecture requests: raise via Head of Department 2 weeks prior\n"
                "Full joining checklist: Faculty Operational Procedures v3, Appendix A"
            ),
            "Admin": (
                "🎓 **Admissions Administration**\n\n"
                "• TNEA quota: 65% seats; Management quota: 35% (Institution discretion)\n"
                "• Admission software: E-seva portal; data synced to ERP post-allotment\n"
                "• Document verification: TN e-verification API integration (go-live June 2025)\n"
                "• Lateral entry (LE): 10 seats/programme; TANCET score required\n"
                "• NRI quota: 3 seats; coordinated with Foreign Relations cell\n"
                "• Merit list publishing: within 48 hrs of TNEA allotment release"
            ),
        }
    ),
    (
        "portal|login|password|erp|system|it|email|wifi|internet|id card|access",
        {
            "Public": (
                "Our institutional systems are accessible to enrolled staff and students. "
                "For IT access or portal queries, contact itsupport@institution.edu."
            ),
            "Student": (
                "💻 **IT & Portal Guide**\n\n"
                "**Student Portal:** portal.institution.edu — use your roll number + DOB (first login)\n"
                "**LMS (Moodle):** lms.institution.edu — same credentials\n"
                "**Email:** rollno@students.institution.edu — 10 GB quota (Google Workspace)\n"
                "**Wi-Fi:** SSID: EduMind-Student | Password shared on portal after registration\n"
                "**ID Card:** Collected from admin office (Photo ID required) during Week 1\n\n"
                "**Common Issues:**\n"
                "• Password reset → portal login page → 'Forgot Password' → OTP to registered mobile\n"
                "• Portal locked → IT helpdesk (Ext. 2100) or itsupport@institution.edu\n"
                "• App: 'EduMind Student' on Play Store / App Store"
            ),
            "Faculty": (
                "🖥️ **Faculty IT Access**\n\n"
                "• Faculty portal: faculty.institution.edu — SAP number + temp password (HR email)\n"
                "• Email: firstname.lastname@institution.edu — 30 GB quota\n"
                "• LMS admin access: course creation rights provisioned by IT on HOD request\n"
                "• Remote desktop: VPN credentials from IT — WFH policy requires approval\n"
                "• Printing: networked printers in each department — credentials from IT\n"
                "• Software licenses: MATLAB, SPSS, AutoCAD available — request via IT portal\n"
                "IT Support: itsupport@institution.edu | Priority ticket for faculty: Ext. 2101"
            ),
            "Admin": (
                "🔧 **IT Administration**\n\n"
                "• ERP: SAP S/4HANA — admin credentials in IT Vault (dual-custody)\n"
                "• Server room: access log reviewed weekly; biometric + PIN required\n"
                "• Backup policy: daily incremental, weekly full; off-site copy to DR centre\n"
                "• Network: 1 Gbps internet (BSNL leased line + Jio backup); monitored 24/7\n"
                "• Cybersecurity: annual penetration testing; last audit: January 2025 (no critical findings)\n"
                "• New user provisioning SLA: 1 working day post-HR confirmation\n"
                "• IT helpdesk ticketing: ServiceNow; SLA — P1 4hrs, P2 8hrs, P3 2 business days"
            ),
        }
    ),
]

# ── Default fallback responses ────────────────────────────────────────────────
DEFAULT_RESPONSES = {
    "Public": (
        "Thank you for your query. As a public visitor, I can provide general information about our institution. "
        "For detailed answers about academics, facilities, and procedures, please sign in with your account. "
        "General enquiries: info@institution.edu | Helpline: 044-2XXX-XXXX (Mon–Sat, 9 AM–5 PM)."
    ),
    "Student": (
        "I searched the institutional knowledge base for your query. For the most accurate and up-to-date "
        "information, please check the student portal or contact the relevant department directly. "
        "You can also raise a helpdesk ticket at support@institution.edu. "
        "Is there a more specific aspect of this topic I can help you with?"
    ),
    "Faculty": (
        "Your query has been searched against the faculty knowledge base and internal SOPs. "
        "For specific procedural details, refer to the Faculty Operational Procedures v3 on the intranet, "
        "or contact your HOD. For urgent administrative matters, contact admin@institution.edu."
    ),
    "Admin": (
        "Your query has been searched across all administrative documents and SOPs. "
        "For matters not covered here, refer to the Administrative Circulars repository or escalate to "
        "the relevant head of function. Contact: admin.helpdesk@institution.edu | Ext. 2001."
    ),
}


def mock_rag_query(query: str, user_role: str) -> dict:
    """Return a role-appropriate answer with relevant source documents."""
    q = query.lower()

    for keywords_str, answers in KNOWLEDGE_BASE:
        keywords = keywords_str.split("|")
        if any(kw in q for kw in keywords):
            answer = answers.get(user_role) or answers.get("Student", DEFAULT_RESPONSES["Student"])
            sources = SOURCES_BY_ROLE.get(user_role, SOURCES_BY_ROLE["Student"])
            return {"answer": answer, "source_documents": sources, "applied_filter": user_role}

    # No topic matched — return friendly default
    return {
        "answer": DEFAULT_RESPONSES.get(user_role, DEFAULT_RESPONSES["Student"]),
        "source_documents": SOURCES_BY_ROLE.get(user_role, []),
        "applied_filter": user_role,
    }


def mock_ingest_document(file_name: str, file_content: bytes) -> bool:
    if not file_name.lower().endswith(".pdf"):
        return False
    if len(file_content) == 0:
        return False
    return True
