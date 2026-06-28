# Repository Assessment & Auditing Report

**Report Generated On:** 2026-06-25 13:29:40

---

## 1. Repository Statistics

* **Total Files Discovered:** 20
* **Total Files Successfully Assessed:** 20
* **Corrupted/Unreadable Files:** 0
* **Empty/Low-Content Files:** 0
* **Duplicate Document Groups:** 0

### File Types Breakdown
| Extension | Count |
| --- | --- |
| `.doc` | 14 |
| `.docx` | 6 |

### Suggested Category Distribution
| Category | Suggested Count |
| --- | --- |
| **SOP** | 20 |

### Represented Academic / Administrative Modules
| Department / Module | Document Count |
| --- | --- |
| Admissions | 1 |
| Research & Development | 1 |
| Alumni | 1 |
| Budgeting | 1 |
| Finance & Accounts | 1 |
| Stores & Purchase | 1 |
| Repair & Maintenance | 1 |
| Security Management | 1 |
| Library Management | 1 |
| Mms | 1 |
| Training & Development | 1 |
| Affiliation Management | 1 |
| Enquiry Handling And Front Office | 1 |
| Fees And Billing | 1 |
| Faculty Recruitment & Evaluation | 1 |
| Academics | 1 |
| Student Activities | 1 |
| Committee | 1 |
| Examination | 1 |
| Training & Placement | 1 |

---

## 2. Integrity Issues Audited

### Duplicate Files (Identical Checksums)
*No binary duplicate files detected in this scan.*

### Potential Version Suffixes & Series
* **Module: Finance & Accounts**:
  * File: `13. VIT Finance & Accounts Final.docx` | Extracted Version: `Final` | Date: `2026-06-25`
* **Module: Fees And Billing**:
  * File: `3.VIT  Fees and Billing(3).docx` | Extracted Version: `3.0` | Date: `2026-06-25`

### Large Documents (> 300KB)
| Filename | Size (KB) | Path |
| --- | --- | --- |
| `10.VIT Research & Development 1.0.doc` | 355.0 KB | `data\10.VIT Research & Development 1.0.doc` |
| `4.VIT Faculty Recruitment & Evaluation.doc` | 403.0 KB | `data\4.VIT Faculty Recruitment & Evaluation.doc` |
| `9. VIT Training & Placement 1.0.doc` | 437.5 KB | `data\9. VIT Training & Placement 1.0.doc` |

### Empty / Low-Text Documents (< 100 characters)
*No empty or low-content files detected.*

### Corrupted or Conversion Failures
*All files parsed and converted successfully without errors.*

---

## 3. Auto-Extracted Documents Inventory & Metadata

| Staging Name | Category | Department / Module | Version | Source Date (FS Fallback) | Access Level |
| --- | --- | --- | --- | --- | --- |
| `1. VIT Admissions.docx` | **SOP** | Admissions | `1.0` | 2026-06-25 | `Public` |
| `10.VIT Research & Development 1.0.docx` | **SOP** | Research & Development | `1.0` | 2026-06-25 | `Public` |
| `11. VIT Alumni 1.0.docx` | **SOP** | Alumni | `1.0` | 2026-06-25 | `Public` |
| `12. VIT Budgeting.docx` | **SOP** | Budgeting | `1.0` | 2026-06-25 | `Public` |
| `13. VIT Finance & Accounts Final.docx` | **SOP** | Finance & Accounts | `Final` | 2026-06-25 | `Public` |
| `14. Stores & Purchase.docx` | **SOP** | Stores & Purchase | `1.0` | 2026-06-25 | `Public` |
| `15. VIT Repair & Maintenance.docx` | **SOP** | Repair & Maintenance | `1.0` | 2026-06-25 | `Public` |
| `16.VIT Security Management.docx` | **SOP** | Security Management | `1.0` | 2026-06-25 | `Public` |
| `17.VIT  Library Management 1.0.docx` | **SOP** | Library Management | `1.0` | 2026-06-25 | `Public` |
| `18. VIT MMS.docx` | **SOP** | Mms | `1.0` | 2026-06-25 | `Public` |
| `20. VIT Training & Development_HR.docx` | **SOP** | Training & Development | `1.0` | 2026-06-25 | `Public` |
| `21. VIT Affiliation Management.docx` | **SOP** | Affiliation Management | `1.0` | 2026-06-25 | `Public` |
| `22. VIT Enquiry Handling and Front Office.docx` | **SOP** | Enquiry Handling And Front Office | `1.0` | 2026-06-25 | `Public` |
| `3.VIT  Fees and Billing(3).docx` | **SOP** | Fees And Billing | `3.0` | 2026-06-25 | `Public` |
| `4.VIT Faculty Recruitment & Evaluation.docx` | **SOP** | Faculty Recruitment & Evaluation | `1.0` | 2026-06-25 | `Public` |
| `5. VIT Academics.docx` | **SOP** | Academics | `1.0` | 2026-06-25 | `Public` |
| `6.VIT Student Activities.docx` | **SOP** | Student Activities | `1.0` | 2026-06-25 | `Public` |
| `7.VIT Committee (1).docx` | **SOP** | Committee | `1.0` | 2026-06-25 | `Public` |
| `8.VIT ExaminationDM.docx` | **SOP** | Examination | `1.0` | 2026-06-25 | `Public` |
| `9. VIT Training & Placement 1.0.docx` | **SOP** | Training & Placement | `1.0` | 2026-06-25 | `Public` |

---

## 4. Suggested Metadata Extraction Rules

Based on document text structure, we recommend the following rules for Phase 2 (Ingestion) extraction:

1. **Category Mapping Rules**:
   * If the first 3 lines contain the words `Standard Operating Procedure` or `SOP`, map as **SOP**.
   * If containing `Policy` or `Guidelines` in the title block, map as **Policy**.
   * Default fallback to folder categorization if matching keywords are absent.
2. **Department Association Rules**:
   * College SOPs represent specific administration modules. Map keyword filters based on first-page text headers (e.g. `Module: Admissions` maps to **Admissions** department).
3. **Version & Revision Control Rules**:
   * Search first page headers or tables for patterns matching `Version [0-9].[0-9]` or `Rev. [0-9].[0-9]` to extract standard version tags.
   * Filenames with `1.0` or similar tags should be normalized, and only the latest verified version sequence should remain active in semantic search queries.
4. **Security/Access Tiers**:
   * Check first page text for keywords like `Confidential`, `Admin Only`, or `Faculty Only`.
   * Propagate this level down to all chunks during the splitting phase.