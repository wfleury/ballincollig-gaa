import csv
from datetime import datetime, timedelta

with open('Ballincollig_Fixtures_Final.csv', newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    rows = list(reader)

print('Columns:', list(rows[0].keys()) if rows else 'empty')
print()

keywords_champ = ['championship', 'cup', 'league cup', 'knockout', 'playoff']
keywords_teams_u14 = ['u14', 'u-14', 'fe14', 'under 14', 'under14']
keywords_teams_u16 = ['u16', 'u-16', 'fe16', 'under 16', 'under16']
keywords_teams_camogie = ['camogie', 'lgfa']

relevant = []
for r in rows:
    date_str = r.get('Date', '') or r.get('date', '')
    competition = (r.get('Competition Name', '') or r.get('Competition', '') or r.get('competition', '')).strip()
    team = (r.get('Team', '') or r.get('team', '')).strip()
    event_type = (r.get('Event Type', '') or '').strip()

    try:
        date = datetime.strptime(date_str.strip(), '%d/%m/%Y')
    except:
        try:
            date = datetime.strptime(date_str.strip(), '%Y-%m-%d')
        except:
            continue

    if not (date.month >= 6 and date.month <= 9 and date.year == 2026):
        continue

    combined = (team + ' ' + competition).lower()
    is_u14 = any(k in combined for k in keywords_teams_u14)
    is_u16 = any(k in combined for k in keywords_teams_u16)
    is_camogie = any(k in combined for k in keywords_teams_camogie)

    if not (is_u14 or is_u16 or is_camogie):
        continue

    is_champ = any(k in competition.lower() for k in keywords_champ) or 'championship' in event_type.lower()
    who = []
    if is_u14: who.append('U14')
    if is_u16: who.append('U16')
    if is_camogie: who.append('Camogie')

    relevant.append({
        'date': date,
        'date_str': date_str.strip(),
        'team': team,
        'competition': competition,
        'is_champ': is_champ,
        'who': '/'.join(who),
        'opponent': (r.get('Opponent', '') or r.get('opponent', '')).strip()
    })

relevant.sort(key=lambda x: x['date'])

print(f'Relevant fixtures (U14/U16/Camogie) June-Sep: {len(relevant)}')
print()
for r in relevant:
    flag = ' *** CHAMP ***' if r['is_champ'] else ''
    print(f"{r['date_str']:12} [{r['who']:7}] {r['competition']:50} vs {r['opponent']}{flag}")

# Now find 7-12 day windows with fewest championship clashes
print()
print('=' * 80)
print('BEST HOLIDAY WINDOWS (7-12 days, fewest championship matches)')
print('=' * 80)

start_search = datetime(2026, 6, 1)
end_search = datetime(2026, 9, 20)

champ_fixtures = [r for r in relevant if r['is_champ']]
all_fixture_dates = set(r['date'].date() for r in relevant)
champ_dates = set(r['date'].date() for r in champ_fixtures)

windows = []
d = start_search
while d <= end_search - timedelta(days=7):
    for length in [7, 8, 9, 10, 11, 12]:
        end = d + timedelta(days=length - 1)
        if end > datetime(2026, 9, 30):
            break
        window_days = set((d + timedelta(days=i)).date() for i in range(length))
        champ_clashes = window_days & champ_dates
        all_clashes = window_days & all_fixture_dates
        windows.append({
            'start': d,
            'end': end,
            'length': length,
            'champ_count': len(champ_clashes),
            'all_count': len(all_clashes),
            'champ_dates': sorted(champ_clashes),
            'all_dates': sorted(all_clashes),
        })
    d += timedelta(days=1)

windows.sort(key=lambda w: (w['champ_count'], w['all_count'], -w['length']))

print()
seen_starts = set()
shown = 0
for w in windows:
    key = (w['start'].date(), w['length'])
    if w['start'].date() in seen_starts:
        continue
    seen_starts.add(w['start'].date())
    label = f"{w['start'].strftime('%d %b')} - {w['end'].strftime('%d %b')} ({w['length']} days)"
    print(f"{label:35} | {w['champ_count']} championship clashes | {w['all_count']} total fixture days")
    if w['champ_dates']:
        clashing = [r for r in champ_fixtures if r['date'].date() in w['champ_dates']]
        for c in clashing:
            print(f"    CHAMP: {c['date_str']} [{c['who']:7}] {c['competition']} vs {c['opponent']}")
    shown += 1
    if shown >= 20:
        break
