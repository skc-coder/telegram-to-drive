import json
import logging
import re
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger("telegram_gdrive_sync")

class PlanResolver:
    def __init__(self, plans_dir: Path):
        self.plans_dir = plans_dir
        self.dbms_mapping = {}
        self.neev_mapping = {}
        self._load_dbms_plan()
        self._load_neev_pdf_planners()

    def _load_dbms_plan(self):
        json_path = self.plans_dir / "course_details.json"
        if not json_path.exists():
            logger.warning(f"course_details.json not found at {json_path}")
            return

        try:
            with open(json_path, encoding="utf-8") as f:
                data = json.load(f)
                for c in data:
                    title = c.get("course_title", "").lower()
                    if "database" in title or "dbms" in title:
                        for item in c.get("syllabus", []):
                            sec = item.get("section", "General").strip()
                            sec = re.sub(r'[/\\?%*:|"<>]', '_', sec)
                            sec = re.sub(r'^\s*Module\s*', '', sec, flags=re.IGNORECASE).strip()
                            
                            code = item.get("code", "").strip()
                            item_name = item.get("name", "").strip()
                            item_title = item.get("title", "").strip()
                            clean_title = item_name if item_name else item_title
                            clean_title = re.sub(r'^\s*(Lecture|LECTURE)\s*-?\s*', '', clean_title, flags=re.IGNORECASE).strip()
                            clean_title = re.sub(r'^\d+[a-z]?\.?\s*', '', clean_title, flags=re.IGNORECASE).strip()

                            m = re.search(r'\b(\d+[a-z]?)\b', item_title, re.IGNORECASE)
                            lec_num = m.group(1).lower() if m else (code.lower() if code else '')

                            key = re.sub(r'[^a-z0-9]', '', clean_title.lower())
                            if key:
                                self.dbms_mapping[key] = (sec, lec_num, clean_title)
        except Exception as e:
            logger.error(f"Error loading DBMS plan: {e}")

    def _load_neev_pdf_planners(self):
        try:
            import pdfplumber
            pdf_files = list(self.plans_dir.glob("*Neev*.pdf")) + list(self.plans_dir.glob("*Planner*.pdf"))
            for pdf_path in pdf_files:
                subj_guess = "General"
                fn_lower = pdf_path.name.lower()
                if "science" in fn_lower:
                    subj_guess = "Science"
                elif "math" in fn_lower:
                    subj_guess = "Maths"
                elif "sst" in fn_lower:
                    subj_guess = "SST"
                elif "hindi" in fn_lower:
                    subj_guess = "Hindi"
                elif "english" in fn_lower:
                    subj_guess = "English"

                with pdfplumber.open(pdf_path) as pdf:
                    for page in pdf.pages:
                        table = page.extract_table()
                        if not table:
                            continue
                        for row in table:
                            row_clean = [c.replace('\n', ' ').strip() if c else '' for c in row]
                            if len(row_clean) >= 4:
                                # Look for chapter and topic columns
                                ch_name = ""
                                topic_name = ""
                                lec_num = ""
                                for cell in row_clean:
                                    if re.match(r'^\d+$', cell) and not lec_num:
                                        lec_num = cell
                                    elif len(cell) > 3 and not ch_name:
                                        ch_name = cell
                                    elif len(cell) > 3 and not topic_name and cell != ch_name:
                                        topic_name = cell
                                
                                if ch_name or topic_name:
                                    comb_name = f"{ch_name} {topic_name}".strip()
                                    key = re.sub(r'[^a-z0-9]', '', comb_name.lower())
                                    if key:
                                        self.neev_mapping[key] = (subj_guess, ch_name, lec_num, topic_name)
        except Exception as e:
            logger.warning(f"Could not parse Neev PDF planners: {e}")

    def resolve_dbms(self, raw_filename: str) -> Tuple[str, str]:
        """Returns (module_subfolder, standardized_filename)"""
        ext = Path(raw_filename).suffix.lower()
        base = Path(raw_filename).stem
        
        # Clean common prefixes
        b_clean = re.sub(r'^\s*(Module\s*\d+\s*|Lecture\s*|Annotated\s*Notes\s*-?\s*)', '', base, flags=re.IGNORECASE).strip()
        b_key = re.sub(r'[^a-z0-9]', '', b_clean.lower())

        is_ann = "annotated" in raw_filename.lower() or "notes" in raw_filename.lower()

        for k, (sec, lec_num, clean_title) in self.dbms_mapping.items():
            if k and (k in b_key or b_key in k):
                prefix = f"Annotated Notes - {lec_num} " if is_ann and lec_num else (f"{lec_num} " if lec_num else "")
                final_name = f"{prefix}{clean_title}{ext}"
                return (sec, final_name)

        # Fallback if unmapped in syllabus
        m_num = re.search(r'\b(\d+[a-z]?)\b', base, re.IGNORECASE)
        num_str = f"{m_num.group(1).lower()} " if m_num else ""
        clean_base = re.sub(r'^\s*(Module\s*\d+\s*|Lecture\s*|Annotated\s*Notes\s*-?\s*)', '', base, flags=re.IGNORECASE).strip()
        clean_base = re.sub(r'^\d+[a-z]?\.?\s*', '', clean_base, flags=re.IGNORECASE).strip()
        prefix = "Annotated Notes - " if is_ann else ""
        return ("General", f"{prefix}{num_str}{clean_base}{ext}")

    def resolve_neev(self, raw_filename: str, text_context: str = "") -> Tuple[str, str]:
        """Returns (subject_subfolder, standardized_filename)"""
        ext = Path(raw_filename).suffix.lower()
        base = Path(raw_filename).stem
        
        # Determine subject
        text_lower = (raw_filename + " " + text_context).lower()
        subj = "SST"
        if "science" in text_lower or "physics" in text_lower or "chemistry" in text_lower or "biology" in text_lower:
            subj = "Science"
        elif "math" in text_lower or "maths" in text_lower:
            subj = "Maths"
        elif "hindi" in text_lower:
            subj = "Hindi"
        elif "english" in text_lower:
            subj = "English"

        is_ann = "notes" in text_lower or "pdf" in ext

        # Standardize name: extract lecture number if present
        m_num = re.search(r'\b(\d+[a-z]?)\b', base, re.IGNORECASE)
        num_str = f"{m_num.group(1).lower()} " if m_num else ""
        
        clean_base = re.sub(r'^\d+_', '', base)  # Remove raw msg prefix e.g. 1714_
        clean_base = re.sub(r'^\d+[a-z]?\.?\s*', '', clean_base, flags=re.IGNORECASE).strip()
        clean_base = re.sub(r'_Class_Notes_.*', '', clean_base, flags=re.IGNORECASE)
        clean_base = re.sub(r'_Recorded_.*', '', clean_base, flags=re.IGNORECASE)
        clean_base = clean_base.replace('_', ' ').strip()
        
        ann_prefix = "Notes - " if is_ann and not clean_base.lower().startswith("notes") else ""
        final_name = f"{ann_prefix}{num_str}{clean_base}{ext}"

        return (subj, final_name)
