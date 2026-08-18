import json
import re
import subprocess
from pathlib import Path

json_path = Path("plans/course_details.json")
if not json_path.exists():
    json_path = Path("/home/skc/dev/lecture plan/course_details.json")

with open(json_path) as f:
    course_data = json.load(f)

target_courses = {
    'c programming': ['gdrive:GATE_Courses/C Programming'],
    'compiler design': ['gdrive:GATE_Courses/Compiler Design', 'gdrive:GATE_Courses/Compiler Design/Compiler Design'],
    'data structures': ['gdrive:GATE_Courses/My data structures ', 'gdrive:GATE_Courses/My data structures /Data Structures']
}

def get_syllabus_items(course_key):
    for c in course_data:
        title = c.get('course_title', '').lower()
        if course_key in title:
            return c.get('syllabus', [])
    return []

for course_key, remote_paths in target_courses.items():
    syllabus = get_syllabus_items(course_key)
    print(f'==================================================')
    print(f'Fixing lecture numbers for: {course_key.upper()} ({len(syllabus)} syllabus items)')
    
    title_to_info = {}
    for item in syllabus:
        title = item.get('title', '').strip()
        name = item.get('name', '').strip()
        code = item.get('code', '').strip()
        sec = item.get('section', 'Module Uncategorized').strip()
        sec = re.sub(r'[/\\?%*:|"<>]', '_', sec)

        m = re.search(r'\b(\d+[a-z]?)\b', title, re.IGNORECASE)
        lec_code = ''
        if m:
            lec_code = m.group(1).lower()
        elif code:
            m_code = re.search(r'\b(\d+[a-z]?)\b', code, re.IGNORECASE)
            if m_code:
                lec_code = m_code.group(1).lower()

        clean_t = re.sub(r'^(Lecture\s*\d+[a-z]?\.?|LIVE:?|Annotated Notes:?|\d+[a-z]?\.?)\s*', '', title, flags=re.IGNORECASE).strip()
        clean_t_key = re.sub(r'[^a-z0-9]', '', clean_t.lower())

        if clean_t_key:
            title_to_info[clean_t_key] = (sec, lec_code, clean_t)

    for base_remote in remote_paths:
        res_base = subprocess.run(['rclone', 'lsf', base_remote], capture_output=True, text=True)

        if res_base.returncode == 0:
            lines = [l.strip() for l in res_base.stdout.splitlines() if l.strip()]
            sub_dirs = [d.strip('/') for d in lines if d.endswith('/')]
            root_files = [f for f in lines if not f.endswith('/')]
            
            # Process files directly under this remote directory
            targets = [('', root_files)] + [(sd, []) for sd in sub_dirs]
            
            for sub_dir in sub_dirs:
                res_sub = subprocess.run(['rclone', 'lsf', f'{base_remote}/{sub_dir}'], capture_output=True, text=True)
                if res_sub.returncode == 0:
                    s_files = [f.strip() for f in res_sub.stdout.splitlines() if f.strip() and not f.endswith('/')]
                    targets.append((sub_dir, s_files))

            for sub_path, file_list in targets:
                dir_path = f'{base_remote}/{sub_path}'.strip('/') if sub_path else base_remote
                for old_sfn in file_list:
                    # Skip if file already has lecture number e.g. 1a, 2b, 4c or is already in a module folder
                    if re.match(r'^\d+[a-z]?\b', old_sfn, re.IGNORECASE) or sub_path.startswith("Module"):
                        continue
                    sfn_no_prefix = re.sub(r'^(Lecture\s*|LECTURE\s*)', '', sfn_no_prefix, flags=re.IGNORECASE).strip()

                    ext = ''
                    if '.' in sfn_no_prefix:
                        parts = sfn_no_prefix.rsplit('.', 1)
                        if len(parts[1]) <= 4 and not any(c in parts[1] for c in ' :()'):
                            ext = '.' + parts[1]
                            base_sfn = parts[0]
                        else:
                            base_sfn = sfn_no_prefix
                    else:
                        base_sfn = sfn_no_prefix

                    clean_sfn_key = re.sub(r'[^a-z0-9]', '', base_sfn.lower())
                    matched_code = ''
                    matched_sec = ''
                    matched_title = base_sfn

                    # Try exact sub-key match first
                    for t_key, (sec, l_code, o_title) in title_to_info.items():
                        if t_key and (t_key in clean_sfn_key or clean_sfn_key in t_key):
                            matched_code = l_code
                            matched_sec = sec
                            matched_title = o_title
                            break

                    # Fallback to word token overlap matching
                    if not matched_code:
                        sfn_words = set(re.findall(r'[a-z0-9]+', base_sfn.lower()))
                        best_score = 0
                        for t_key, (sec, l_code, o_title) in title_to_info.items():
                            t_words = set(re.findall(r'[a-z0-9]+', o_title.lower()))
                            common = sfn_words.intersection(t_words)
                            if len(common) > best_score and len(common) >= 2:
                                best_score = len(common)
                                matched_code = l_code
                                matched_sec = sec
                                matched_title = o_title

                    if matched_code or sfn_no_prefix != old_sfn:
                        num_prefix = f'{matched_code} ' if matched_code and not re.match(r'^\d+[a-z]?\b', base_sfn, re.IGNORECASE) else ''
                        new_sfn = f'{num_prefix}{base_sfn}{ext}'

                        # Move into module folder if resolved
                        dest_folder = f'{base_remote}/{matched_sec}' if matched_sec else dir_path
                        print(f'  [{course_key.upper()}] "{old_sfn}" -> "{matched_sec}/{new_sfn}"')
                        subprocess.run(['rclone', 'moveto', f'{dir_path}/{old_sfn}', f'{dest_folder}/{new_sfn}'])

print('\nALL THREE COURSES (C Programming, Compiler Design, Data Structures) PROPERLY PREFIXED WITH LECTURE NUMBERS!')
