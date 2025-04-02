# --- Import necessary libraries ---
from flask import Flask, request, render_template_string, Response, session
import requests
from bs4 import BeautifulSoup
import re
import csv
import io
import os # Needed for generating/accessing secret key

# --- Initialize the Flask Application ---
app = Flask(__name__)

# --- Configure the Secret Key ---
# Flask sessions require a secret key for security.
# It's best practice to load this from an environment variable.
# Render.com allows you to set environment variables in your service settings.
# We provide a default key here ONLY for local development if the environment variable isn't set.
# **IMPORTANT:** Replace 'a_very_default_development_secret_key_replace_me' with a real random key
#               or better yet, ONLY rely on the environment variable in production.
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'a_very_default_development_secret_key_replace_me')

# --- Helper function to parse pasted text from USA Fencing ---
def parse_usafencing_text(pasted_text):
    lines = pasted_text.split('\n')
    fencers = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        # Basic check for a name format (often includes a comma)
        if ',' in line:
            # Look ahead a few lines to see if the USA flag emoji exists,
            # which often indicates a fencer entry block in copied text.
            lookahead_lines = [lines[j].strip() for j in range(i + 1, min(i + 4, len(lines)))]
            if any('🇺🇸' in la_line for la_line in lookahead_lines):
                name = line
                club = ''
                # Try to find the club name, which often follows the flag line
                j = i + 1
                while j < len(lines):
                    next_line = lines[j].strip()
                    if '🇺🇸' in next_line:
                        club_line_index = j + 1
                        if club_line_index < len(lines):
                            # Clean up potential rating characters often found in club lines
                            club_line = lines[club_line_index].strip()
                            club = re.sub(r'#\d+', '', club_line).strip() # Remove things like '#1 '
                        break # Found the block, move to next potential fencer
                    j += 1
                fencers.append((name, club))
                i = j # Move the main index past the processed block
            else:
                i += 1 # Not a fencer block, move to the next line
        else:
            i += 1 # Line doesn't look like a name, move to the next line
    return fencers

# --- Main Route for the Web Page ---
@app.route('/', methods=['GET', 'POST'])
def index():
    # Initialize variables for rendering the page
    events = {}       # To store AskFred event data {event_name: {fencer_display: profile_url}}
    usa_fencers = []  # To store parsed USA Fencing data [(name, club)]
    csv_data_for_session = [] # Temporary list to build data for CSV/session

    # Handle form submission
    if request.method == 'POST':
        askfred_url = request.form.get('askfred_url')
        pasted_text = request.form.get('pasted_text')

        if askfred_url:
            try:
                page = requests.get(askfred_url, timeout=10) # Added timeout
                page.raise_for_status() # Check for HTTP errors
                soup = BeautifulSoup(page.content, 'html.parser')
                # Find event sections (adjust selectors if AskFred structure changes)
                event_sections = soup.find_all('div', class_='card-body p-0')

                for event_section in event_sections:
                    header = event_section.find_previous('div', class_='card-header')
                    event_name = header.get_text(strip=True) if header else "Unnamed Event"
                    event_fencers = {} # Fencers for this specific event

                    table = event_section.find('table', class_='preregistration-list')
                    if table and table.find('tbody'):
                        rows = table.find('tbody').find_all('tr')
                        for row in rows:
                            cells = row.find_all('td')
                            # Ensure row has enough cells (Name is often index 1, Club index 2)
                            if len(cells) >= 3:
                                name = cells[1].get_text(strip=True)
                                club = cells[2].get_text(strip=True)
                                # Create a search URL for Fencing Tracker
                                name_query = '+'.join(name.split())
                                profile_url = f"https://fencingtracker.com/search?s={name_query}"
                                # Store for display and for CSV export
                                event_fencers[f"{name} ({club})"] = profile_url # Store display text as key
                                csv_data_for_session.append([name, club, profile_url]) # Store raw data for CSV

                    if event_fencers: # Only add event if fencers were found
                         events[event_name] = event_fencers

            except requests.exceptions.RequestException as e:
                # Handle errors fetching URL (e.g., invalid URL, timeout, network issue)
                # You might want to display this error to the user
                print(f"Error fetching AskFred URL: {e}")
                # Optionally pass an error message to the template
            except Exception as e:
                # Catch other potential parsing errors
                print(f"Error processing AskFred data: {e}")

        elif pasted_text:
            try:
                # Parse the pasted text using the helper function
                parsed_fencers = parse_usafencing_text(pasted_text)
                usa_fencers = [] # Reset or initialize for display
                # Prepare data for display AND CSV export from the parsed text
                for name, club in parsed_fencers:
                    name_query = '+'.join(name.split())
                    profile_url = f"https://fencingtracker.com/search?s={name_query}"
                    usa_fencers.append({'name': name, 'club': club, 'url': profile_url}) # Store structured data for display
                    csv_data_for_session.append([name, club, profile_url]) # Store raw data for CSV
            except Exception as e:
                 # Catch potential errors during text parsing
                 print(f"Error processing pasted text: {e}")


        # --- Store the collected CSV data in the user's session ---
        session['csv_data'] = csv_data_for_session

    # --- Render the HTML page ---
    # Pass the processed data (events, usa_fencers) to the template
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
            textarea { resize: vertical; min-height: 100px; }
            .copy-target small { color: #6c757d; display: block; } /* Style club name, make it block */
            .list-group-item { padding-bottom: 0.5rem; } /* Adjust padding */
            .list-group-item a { display: block; margin-bottom: 0.25rem; } /* Link display */
        </style>
    </head>
    <body>
        <div class="container">
            <h2 class="mb-4">Fencing Profile Linker</h2>

            <form method="post">
                <div class="mb-3">
                    <label for="askfred_url_input" class="form-label">AskFred.net Tournament URL:</label>
                    <input type="url" id="askfred_url_input" name="askfred_url" class="form-control" placeholder="https://www.askfred.net/tournaments/...">
                </div>

                <div class="text-center my-3">— OR —</div>

                <div class="mb-3">
                    <label for="pasted_text_input" class="form-label">Paste USA Fencing Entrants:</label>
                    <textarea id="pasted_text_input" name="pasted_text" rows="5" class="form-control" placeholder="On the USA Fencing entrants page: On Desktop, carefully select *only* the list of fencers with your mouse. On Mobile, 'Select All' might work better. Then Copy (Ctrl+C or Cmd+C) and Paste here."></textarea>
                    <div class="form-text">Try to copy only the names/clubs/ratings. Extra text might interfere with parsing.</div>
                </div>

                <div class="d-flex justify-content-between align-items-center mt-4">
                    <button type="submit" class="btn btn-primary">Generate Links</button>
                    {% if session.get('csv_data') %}
                    <div>
                        <a href="/export_csv" class="btn btn-outline-secondary">Export CSV</a>
                        <button type="button" class="btn btn-outline-secondary" onclick="copyLinks()">Copy All Data</button>
                    </div>
                    {% endif %}
                </div>
            </form>

            {% set display_data = session.get('csv_data', []) %}
            {% if display_data and request.form.get('askfred_url') %}
                <div class="mt-4">
                    <h4>AskFred Results</h4>
                     <ul class="list-group copy-target">
                        {% for name, club, url in display_data %}
                        <li class="list-group-item" data-name="{{ name }}" data-club="{{ club }}" data-url="{{ url }}">
                             <a href="{{ url }}" target="_blank" rel="noopener noreferrer">{{ name }}</a>
                             <small>{{ club if club else 'Club not specified' }}</small>
                         </li>
                        {% else %}
                         <li class="list-group-item">No fencers found or processed for this event.</li>
                        {% endfor %}
                    </ul>
                </div>
            {% elif display_data and request.form.get('pasted_text') %}
                 <div class="mt-4">
                    <h4>USA Fencing Entrants</h4>
                    <ul class="list-group copy-target">
                        {% for name, club, url in display_data %}
                         <li class="list-group-item" data-name="{{ name }}" data-club="{{ club }}" data-url="{{ url }}">
                             <a href="{{ url }}" target="_blank" rel="noopener noreferrer">{{ name }}</a>
                             <small>{{ club if club else 'Club not found' }}</small>
                         </li>
                        {% else %}
                        <li class="list-group-item">No fencers processed from pasted text.</li>
                        {% endfor %}
                    </ul>
                </div>
            {% endif %}

        </div>

        <script>
        function copyLinks() {
            // Select all list items that contain the data attributes
            const listItems = document.querySelectorAll('.copy-target li[data-name]');
            if (listItems.length === 0) {
                alert("No data found to copy.");
                return;
            }

            // Create text output: Name<Tab>Club<Tab>URL
            // Using Tab as a separator makes it easy to paste into spreadsheets
            const outputText = Array.from(listItems).map(item => {
                const name = item.getAttribute('data-name');
                const club = item.getAttribute('data-club') || ''; // Use empty string if club is missing
                const url = item.getAttribute('data-url');
                return `${name}\t${club}\t${url}`; // Use Tab separators
            }).join('\\n'); // Newline between entries

            navigator.clipboard.writeText(outputText)
                .then(() => alert(listItems.length + " fencer entries copied to clipboard!"))
                .catch(err => alert("Failed to copy data: " + err));
        }
        </script>
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    </body>
    </html>
    """, events=events, usa_fencers=usa_fencers) # Pass data to template


# --- Route for Exporting CSV Data ---
@app.route('/export_csv')
def export_csv():
    # --- Retrieve the data stored in the session ---
    # Use .get with a default empty list in case 'csv_data' is not in the session
    data_to_export = session.get('csv_data', [])

    # Use StringIO to create a file-like object in memory
    output = io.StringIO()
    writer = csv.writer(output)

    # --- Write the header row (matches clipboard format conceptually) ---
    writer.writerow(['Name', 'Club', 'FencingTracker Search URL'])

    # --- Write the actual data retrieved from the session ---
    if data_to_export:
        writer.writerows(data_to_export)
    else:
        # Optional: Write a placeholder if no data exists
        writer.writerow(['No data available for export.', '', ''])

    # Go back to the start of the StringIO object
    output.seek(0)

    # Create a response object with the CSV data
    return Response(
        output,
        mimetype='text/csv',
        headers={"Content-Disposition": "attachment;filename=fencers_export.csv"} # Suggest a filename
    )

# --- Run the Flask App ---
if __name__ == '__main__':
    # Render.com and many other platforms set the PORT environment variable.
    # Default to 8080 if it's not set (useful for some local testing).
    port = int(os.environ.get('PORT', 8080))
    # Host '0.0.0.0' makes it accessible externally (needed for Render).
    app.run(host='0.0.0.0', port=port)