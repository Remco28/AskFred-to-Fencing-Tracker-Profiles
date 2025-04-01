from flask import Flask, request, render_template_string
import requests
from bs4 import BeautifulSoup
import re

app = Flask(__name__)

def parse_usafencing_text(pasted_text):
    lines = pasted_text.split('\n')
    fencers = []

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        if ',' in line:
            name = line
            club = ''

            j = i + 1
            while j < len(lines):
                next_line = lines[j].strip()
                if '🇺🇸' in next_line:
                    club_line_index = j + 1
                    if club_line_index < len(lines):
                        club_line = lines[club_line_index].strip()
                        club = re.sub(r'#\d+', '', club_line).strip()
                    break
                j += 1

            fencers.append((name, club))
            i = j
        else:
            i += 1

    return fencers

@app.route('/', methods=['GET', 'POST'])
def index():
    events = {}
    usa_fencers = []

    if request.method == 'POST':
        askfred_url = request.form.get('askfred_url')
        pasted_text = request.form.get('pasted_text')

        if askfred_url:
            page = requests.get(askfred_url)
            soup = BeautifulSoup(page.content, 'html.parser')
            event_sections = soup.find_all('div', class_='card-body p-0')

            for event in event_sections:
                header = event.find_previous('div', class_='card-header')
                event_name = header.get_text(strip=True) if header else "Unnamed Event"

                fencers = {}
                table = event.find('table', class_='preregistration-list')
                if table:
                    rows = table.find('tbody').find_all('tr')
                    for row in rows:
                        cells = row.find_all('td')
                        if len(cells) >= 3:
                            name = cells[1].get_text(strip=True)
                            club = cells[2].get_text(strip=True)
                            name_query = '+'.join(name.split())
                            profile_url = f"https://fencingtracker.com/search?s={name_query}"
                            fencers[f"{name} ({club})"] = profile_url

                events[event_name] = fencers

        elif pasted_text:
            usa_fencers = parse_usafencing_text(pasted_text)

    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Fencing Profile Linker</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
          body { padding-top: 20px; padding-bottom: 50px; }
          .container { max-width: 700px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h2 class="mb-4">Fencing Profile Linker</h2>

            <form method="post">
                <div class="mb-3">
                    <label class="form-label">AskFred.net Tournament URL:</label>
                    <input type="url" name="askfred_url" class="form-control" placeholder="https://www.askfred.net/...">
                </div>

                <div class="text-center my-3">— or —</div>

                <div class="mb-3">
                    <label class="form-label">USA Fencing Entrants:</label>
                    <textarea name="pasted_text" rows="5" class="form-control" placeholder="Open the Entrants page for the event. Then 'select all' and copy the whole thing into this box."></textarea>
                </div>

                <button type="submit" class="btn btn-primary">Generate Links</button>
            </form>

            {% if events %}
                {% for event, links in events.items() %}
                <div class="mt-4">
                    <h4>{{ event }}</h4>
                    <ul class="list-group">
                        {% for name, link in links.items() %}
                        <li class="list-group-item"><a href="{{ link }}" target="_blank">{{ name }}</a></li>
                        {% endfor %}
                    </ul>
                </div>
                {% endfor %}
            {% endif %}

            {% if usa_fencers %}
                <div class="mt-4">
                    <h4>USA Fencing Entrants</h4>
                    <ul class="list-group">
                        {% for name, club in usa_fencers %}
                        <li class="list-group-item">
                            <a href="https://fencingtracker.com/search?s={{ '+'.join(name.split()) }}" target="_blank">{{ name }}</a><br>
                            <small>{{ club }}</small>
                        </li>
                        {% endfor %}
                    </ul>
                </div>
            {% endif %}
        </div>

        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    </body>
    </html>
    """, events=events, usa_fencers=usa_fencers)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
