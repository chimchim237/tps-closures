"""Add feeder patterns, consolidation groups and welcoming sites to data/schools.geojson.

Sources:
- Feeder membership: Tulsa Public Schools, "Elementary" and "Middle Schools" pages under
  tulsaschools.org/enrollment/our-schools (feeder-pattern headings), read 22 Sep 2026.
- Groups, welcoming sites, headcounts and feeder shifts: TPS, Superintendent's Proposal to
  Address Budget Deficit, 21 Sep 2026, slides 28-46.
Run from the repo root: python3 tools/add_feeders_groups.py
"""
import json, pathlib

P = pathlib.Path(__file__).resolve().parent.parent / 'data' / 'schools.geojson'
d = json.loads(P.read_text())

FEEDER = {
  'Hale': ['bell-elementary', 'hamilton-elementary', 'hoover-elementary', 'kendall-whittier-elementary',
           'lindbergh-elementary', 'macarthur-elementary', 'mckinley-elementary', 'owen-elementary',
           'skelly-elementary', 'hale-middle-school', 'nathan-hale-high-school'],
  'Central': ['burroughs-elementary', 'emerson-montessori', 'greenwood-leadership-academy',
              'wayman-tisdale-fine-arts-academy', 'central-middle-school', 'central-high-school'],
  'East Central': ['cooper-elementary', 'disney-elementary', 'dolores-huerta-elementary', 'kerr-elementary',
                   'lewis-and-clark-elementary', 'mitchell-elementary', 'peary-elementary',
                   'east-central-high-school', 'east-central-middle-school'],
  'McLain': ['anderson-elementary', 'celia-clinton-elementary', 'hawthorne-elementary',
             'john-hope-franklin-elementary', 'sequoyah-elementary', 'springdale-elementary',
             'unity-learning-academy', 'whitman-elementary', 'mclain-high-school', 'monroe-demonstration-academy'],
  'Edison': ['council-oak-elementary', 'eliot-elementary', 'lanier-elementary', 'patrick-henry-elementary',
             'edison-preparatory-high', 'edison-preparatory-middle'],
  'Memorial': ['carnegie-elementary', 'grissom-elementary', 'key-elementary', 'marshall-elementary',
               'mcclure-elementary', 'salk-elementary', 'memorial-high-school', 'memorial-middle-school'],
  'Webster': ['clinton-west-elementary', 'eugene-field-elementary', 'robertson-elementary',
              'webster-high-school', 'webster-middle-school'],
  'Magnet': ['booker-t-washington-high', 'carver-middle-school', 'eisenhower-international',
             'felicitas-mendez-international', 'zarrow-international', 'mayo-demonstration-academy',
             'thoreau-demonstration-academy', 'rogers-college-high', 'rogers-college-middle'],
  'Alternative': ['tulsa-met-ms-hs', 'traice-academy-ms-and-hs', 'tulsa-virtual-academy-ms-and-hs', 'soar',
                  'phoenix-rising', 'new-vision-academy', 'north-star-academy', 'street-school',
                  'tulsa-transition-academy'],
  'Charter': ['college-bound-academy-–-brookside', 'college-bound-academy-–-eastside',
              'kipp-tulsa-college-preparatory', 'kipp-tulsa-university-prep', 'tulsa-honor-academy-high',
              'tulsa-honor-academy-middle', 'tulsa-honor-academy-–-flores-ms', 'tulsa-legacy-charter:-primary',
              'tulsa-legacy-charter:-upper', 'tulsa-school-of-arts-and-sciences-hs',
              'tulsa-school-of-arts-and-sciences-ms', 'under-the-canopy-school'],
}

# slide 45: feeder shifts under the proposal
SHIFT = {
  'wayman-tisdale-fine-arts-academy': ('Webster', None),
  'burroughs-elementary': ('McLain', None),
  'emerson-montessori': ('McLain', None),
  'owen-elementary': ('McLain', None),
  'hamilton-elementary': ('East Central', None),
  'salk-elementary': ('Hale', 'north of 51st Street only'),
  'central-high-school': ('Alternative', 'becomes the Alternative High School Hub'),
}

# slides 28-42: consolidation groups, welcoming sites, headcounts (group totals)
GROUPS = [
  ('Elementary group 1', 854, 686, {
    'anderson-elementary': ['hawthorne-elementary', 'whitman-elementary'],
    'greenwood-leadership-academy': ['wayman-tisdale-fine-arts-academy', 'burroughs-elementary'],
    'unity-learning-academy': ['celia-clinton-elementary', 'hamilton-elementary']}),
  ('Elementary group 2', 658, 550, {
    'springdale-elementary': ['felicitas-mendez-international', 'hawthorne-elementary', 'celia-clinton-elementary'],
    'sequoyah-elementary': ['kendall-whittier-elementary', 'owen-elementary', 'felicitas-mendez-international']}),
  ('Elementary group 3', 941, 792, {
    'mitchell-elementary': ['hamilton-elementary', 'mckinley-elementary'],
    'kerr-elementary': ['lewis-and-clark-elementary', 'cooper-elementary'],
    'bell-elementary': ['macarthur-elementary', 'mckinley-elementary']}),
  ('Elementary group 4', 538, 443, {
    'key-elementary': ['salk-elementary', 'carnegie-elementary'],
    'marshall-elementary': ['mcclure-elementary']}),
  ('Elementary group 5', 787, 732, {
    'dolores-huerta-elementary': ['skelly-elementary', 'disney-elementary'],
    'hoover-elementary': ['skelly-elementary', 'macarthur-elementary'],
    'peary-elementary': ['cooper-elementary', 'disney-elementary']}),
  ('Elementary group 6', 228, 181, {
    'robertson-elementary': ['clinton-west-elementary']}),
  # slide 42 reports Secondary groups 1 and 2 together: 720 students, 653 families
  ('Secondary group 1', 720, 653, {
    'thoreau-demonstration-academy': [],
    'tulsa-met-ms-hs': []}),
  ('Secondary group 2', 720, 653, {
    'central-middle-school': ['monroe-demonstration-academy', 'webster-middle-school']}),
]
SECONDARY_NOTE = 'Students return to their home school or choose a school in the 2027-28 enrollment window.'

by = {f['properties']['id']: f['properties'] for f in d['features']}
feeder_of = {sid: name for name, ids in FEEDER.items() for sid in ids}
missing = [i for i in by if i not in feeder_of]
assert not missing, missing
unknown = [i for i in feeder_of if i not in by]
assert not unknown, unknown

for sid, p in by.items():
    p['feeder'] = feeder_of[sid]
    p.pop('feeder_proposed', None); p.pop('feeder_note', None)
    p.pop('group', None); p.pop('group_students', None); p.pop('group_families', None)
    p.pop('welcoming', None); p.pop('receives_from', None); p.pop('welcoming_note', None)
    if sid in SHIFT:
        p['feeder_proposed'], note = SHIFT[sid]
        if note: p['feeder_note'] = note

for name, students, families, members in GROUPS:
    for sid, welcome in members.items():
        p = by[sid]
        p['group'] = name; p['group_students'] = students; p['group_families'] = families
        p['welcoming'] = welcome
        if not welcome: p['welcoming_note'] = SECONDARY_NOTE
        for w in welcome:
            by[w].setdefault('receives_from', [])
            if sid not in by[w]['receives_from']: by[w]['receives_from'].append(sid)

closures = [p for p in by.values() if p['status'] == 'closure']
assert all('group' in p for p in closures), [p['id'] for p in closures if 'group' not in p]

P.write_text(json.dumps(d, ensure_ascii=False, indent=1) + '\n')
print(len(by), 'schools;', sum('welcoming' in p for p in by.values()), 'closures with groups;',
      sum('receives_from' in p for p in by.values()), 'welcoming sites')
