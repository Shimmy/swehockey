from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
from swehockey import SwehockeyAPI
from announcer import HockeyAnnouncer  # Adjust as needed
from elevenlabs.client import ElevenLabs
import json
import os
from datetime import datetime
import jinja2
from io import BytesIO

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Global variables
current_game = None
api = SwehockeyAPI()
announcer = HockeyAnnouncer(language="sv")
tts_client = ElevenLabs(api_key=os.getenv('ELEVENLABS_API_KEY'))  # Ensure API key is set in environment

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/load_game', methods=['POST'])
def load_game():
    global current_game, api
    
    game_id = request.form.get('game_id')
    if not game_id:
        flash('Please enter a game ID', 'danger')
        return redirect(url_for('index'))
    
    try:
        game_id = int(game_id)
        current_game = api.load_game(game_id)
        return redirect(url_for('summary'))
    except ValueError:
        flash('Game ID must be a number', 'danger')
        return redirect(url_for('index'))
    except Exception as e:
        flash(f'Error loading game: {str(e)}', 'danger')
        return redirect(url_for('index'))

@app.route('/summary')
def summary():
    if current_game is None:
        flash('No game loaded', 'warning')
        return redirect(url_for('index'))
    return render_template('summary.html', game=current_game)

@app.route('/lineups')
def lineups():
    if current_game is None:
        flash('No game loaded', 'warning')
        return redirect(url_for('index'))
    lineups_announce = announcer.announce_lineups(current_game)
    welcome_announce = announcer.announce_welcome(current_game)
    return render_template('lineups.html', game=current_game, lineups_announce=lineups_announce, welcome_announce=welcome_announce)

@app.route('/actions')
def actions():
    global announcer
    if current_game is None:
        flash('No game loaded', 'warning')
        return redirect(url_for('index'))
    
    for event in current_game['events']:
        event['announcement'] = announcer.announce_event(event, current_game)
    
    return render_template('actions.html', game=current_game)

@app.route('/refresh/<refresh_type>')
def refresh(refresh_type):
    global current_game, api
    
    if current_game is None:
        flash('No game loaded', 'warning')
        return redirect(url_for('index'))
    
    try:
        if refresh_type == 'summary':
            current_game = api.refresh_summary()
            flash('Summary data refreshed', 'success')
            return redirect(url_for('summary'))
        elif refresh_type == 'lineups':
            current_game = api.refresh_lineups()
            flash('Lineup data refreshed', 'success')
            return redirect(url_for('lineups'))
        elif refresh_type == 'actions':
            current_game = api.refresh_actions()
            for event in current_game['events']:
                event['announcement'] = announcer.announce_event(event, current_game)
            flash('Actions data refreshed', 'success')
            return redirect(url_for('actions'))
        elif refresh_type == 'all':
            current_game = api.refresh_all()
            for event in current_game['events']:
                event['announcement'] = announcer.announce_event(event, current_game)
            flash('All game data refreshed', 'success')
            return redirect(url_for('summary'))
        else:
            flash('Invalid refresh type', 'danger')
            return redirect(url_for('summary'))
    except Exception as e:
        flash(f'Error refreshing data: {str(e)}', 'danger')
        return redirect(url_for('summary'))

@app.route('/tts', methods=['POST'])
def text_to_speech():
    global tts_client
    text = request.form.get('text')
    if not text:
        return jsonify({'error': 'No text provided'}), 400
    
    try:
        # Get the audio generator from ElevenLabs
        text = text.replace("Haninge Anchors HC Röd", "Haninge")
        text = text.replace("IFK Österåker Hockey", "Österåker")
        audio_generator = tts_client.text_to_speech.convert(
            text=text,
            voice_id="FF7KdobWPaiR0vkcALHF",  # Swedish voice ID
            model_id="eleven_multilingual_v2",
            output_format="mp3_44100_128",
        )
        
        # Collect all chunks from the generator into a single bytes object
        audio_bytes = b''.join(audio_generator)
        
        # Return the audio as a file response
        return send_file(
            BytesIO(audio_bytes),
            mimetype='audio/mp3',
            as_attachment=False,
            download_name='announcement.mp3'
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Template filters remain unchanged
@app.template_filter('format_time')
def format_time(time_str):
    minutes, seconds = time_str.split(':')
    return f"{minutes.zfill(2)}:{seconds.zfill(2)}"

@app.template_filter('format_duration')
def format_duration(minutes):
    if not minutes:
        return ''
    return f"{minutes} min"

@app.template_filter('format_datetime')
def format_datetime(date_str):
    if not date_str:
        return ''
    try:
        dt = datetime.fromisoformat(date_str)
        return dt.strftime('%Y-%m-%d %H:%M')
    except:
        return date_str

@app.template_filter('event_color')
def event_color(event_type):
    colors = {
        'goal': 'success',
        'penalty': 'danger',
        'goalie-in': 'info',
        'goalie-out': 'secondary',
        'timeout': 'warning'
    }
    return colors.get(event_type, 'primary')

@app.template_filter('team_class')
def team_class(team_side):
    return 'home-team' if team_side == 'home' else 'away-team'

if __name__ == '__main__':
    app.run(debug=True)