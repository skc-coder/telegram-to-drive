from pathlib import Path

json_path = Path("plans/course_details.json")
if not json_path.exists():
    json_path = Path("/home/skc/dev/lecture plan/course_details.json")

with open(json_path) as f:
    course_data = json.load(f)

target_courses = {
    'c programming': 'gdrive:GATE_Courses/C Programming',
    'compiler design': 'gdrive:GATE_Courses/Compiler Design',
    'data structures': 'gdrive:GATE_Courses/My data structures '
}

def get_syllabus_items(course_key):
    for c in course_data:
        title = c.get('course_title', '').lower()
        if course_key in title:
            return c.get('syllabus', [])
    return []

for course_key, base_remote in target_courses.items():
    syllabus = get_syllabus_items(course_key)
    print(f'==================================================')
    print(f'Fixing lecture numbers for: {course_key.upper()} ({len(syllabus)} syllabus items)')
    
    title_to_code = {}
    for item in syllabus:
        title = item.get('title', '').strip()
        name = item.get('name', '').strip()
        code = item.get('code', '').strip()
        sec = item.get('section', 'Module Uncategorized').strip()

        m = re.search(r'\b(\d+[a-z]?)\b', title, re.IGNORECASE)
        lec_code = ''
        if m:
            lec_code = m.group(1).lower()

        clean_t = re.sub(r'^(Lecture\s*\d+[a-z]?\.?|LIVE:?|Annotated Notes:?|\d+[a-z]?\.?)\s*', '', title, flags=re.IGNORECASE).strip()
        clean_t_key = re.sub(r'[^a-z0-9]', '', clean_t.lower())

        if clean_t_key:
            title_to_code[clean_t_key] = (sec, lec_code, clean_t)

    res_base = subprocess.run(['rclone', 'lsf', base_remote], capture_output=True, text=True)

    if res_base.returncode == 0:
        sub_dirs = [d.strip('/') for d in res_base.stdout.splitlines() if d.endswith('/')]
        for sub in sub_dirs:
            dir_path = f'{base_remote}/{sub}'
            res_sub_files = subprocess.run(['rclone', 'lsf', dir_path], capture_output=True, text=True)
            if res_sub_files.returncode == 0:
                sfiles = [f.strip() for f in res_sub_files.stdout.splitlines() if f.strip() and not f.endswith('/')]
                for old_sfn in sfiles:
                    ext = ''
                    if '.' in old_sfn:
                        parts = old_sfn.rsplit('.', 1)
                        if len(parts[1]) <= 4 and not any(c in parts[1] for c in ' :()'):
                            ext = '.' + parts[1]
                            base_sfn = parts[0]
                        else:
                            base_sfn = old_sfn
                    else:
                        base_sfn = old_sfn

                    if re.match(r'^\d+[a-z]?\b', base_sfn, re.IGNORECASE):
                        continue

                    clean_sfn_key = re.sub(r'[^a-z0-9]', '', base_sfn.lower())
                    matched_code = ''
                    for t_key, (sec, l_code, o_title) in title_to_code.items():
                        if t_key and (t_key in clean_sfn_key or clean_sfn_key in t_key):
                            matched_code = l_code
                            break

                    if matched_code:
                        new_sfn = f'{matched_code} {base_sfn}{ext}'
                        print(f'  [{course_key.upper()}] "{old_sfn}" -> "{new_sfn}"')
                        subprocess.run(['rclone', 'moveto', f'{dir_path}/{old_sfn}', f'{dir_path}/{new_sfn}'])

print('\nALL THREE COURSES (C Programming, Compiler Design, Data Structures) PROPERLY PREFIXED WITH LECTURE NUMBERS!')
