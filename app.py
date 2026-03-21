from flask import Flask, render_template, request, jsonify
import pandas as pd
import json
import plotly.graph_objects as go
import plotly.express as px
import threading
import time
from datetime import datetime

import simulation

app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False

# Global state for async runs
sim_state = {'running': False, 'progress': 0, 'result': None, 'error': None}


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/run', methods=['POST'])
def run_simulation():
    """API endpoint to run simulation asynchronously."""
    global sim_state
    
    if sim_state['running']:
        return jsonify({'error': 'Simulation already running'}), 400
    
    data = request.json
    try:
        num_doctors = int(data.get('num_doctors', 3))
        avg_arrival = float(data.get('avg_arrival', 10))
        sim_time = float(data.get('sim_time', 480))
        num_replications = int(data.get('num_replications', 1))
        
        # Validate inputs
        if num_doctors < 1 or num_doctors > 20:
            return jsonify({'error': 'Staff must be 1-20'}), 400
        if avg_arrival < 0.1 or avg_arrival > 60:
            return jsonify({'error': 'Arrival rate must be 0.1-60 min'}), 400
        if sim_time < 10 or sim_time > 10000:
            return jsonify({'error': 'Sim time must be 10-10000 min'}), 400
        
        # Run in background thread
        sim_state = {'running': True, 'progress': 0, 'result': None, 'error': None}
        thread = threading.Thread(target=_run_sim_bg, args=(num_doctors, avg_arrival, sim_time, num_replications))
        thread.daemon = True
        thread.start()
        
        return jsonify({'status': 'started'})
    except Exception as e:
        sim_state = {'running': False, 'progress': 0, 'result': None, 'error': str(e)}
        return jsonify({'error': str(e)}), 500


def _run_sim_bg(num_doctors, avg_arrival, sim_time, num_replications):
    """Run simulation in background."""
    global sim_state
    try:
        all_data = []
        for i in range(num_replications):
            sim_state['progress'] = int((i / num_replications) * 100)
            df = simulation.run_simulation(num_doctors, avg_arrival, sim_time, seed=None)
            df['Replication'] = i + 1
            all_data.append(df)
            time.sleep(0.1)  # Prevent blocking
        
        df_combined = pd.concat(all_data, ignore_index=True)
        sim_state = {
            'running': False,
            'progress': 100,
            'result': df_combined.to_json(date_format='iso', orient='split'),
            'error': None
        }
    except Exception as e:
        sim_state = {'running': False, 'progress': 0, 'result': None, 'error': str(e)}


@app.route('/api/status', methods=['GET'])
def get_status():
    """Check current simulation status."""
    return jsonify(sim_state)


@app.route('/api/results', methods=['GET'])
def get_results():
    """Fetch latest results."""
    if sim_state['result']:
        df = pd.read_json(sim_state['result'], orient='split')
        
        # Generate charts
        fig_box = px.box(df, x='Severity', y='Wait Time (min)', color='Severity',
                         color_discrete_map={"🔴 Emergency": "red", "🟡 Urgent": "orange", "🟢 Non-Urgent": "green"},
                         title="Wait Time Distribution by Severity")
        
        throughput_df = df.groupby('Severity').size().reset_index(name='Count')
        fig_pie = px.pie(throughput_df, values='Count', names='Severity', hole=0.4,
                         color='Severity', color_discrete_map={"🔴 Emergency": "red", "🟡 Urgent": "orange", "🟢 Non-Urgent": "green"},
                         title="Patient Throughput")
        
        # Wait time over time
        fig_line = px.line(df.sort_values('ID'), x='ID', y='Wait Time (min)', 
                           color='Severity', title="Wait Times Over Simulation",
                           color_discrete_map={"🔴 Emergency": "red", "🟡 Urgent": "orange", "🟢 Non-Urgent": "green"})
        
        # Metrics
        metrics = {
            'total_patients': int(len(df)),
            'avg_wait': round(df['Wait Time (min)'].mean(), 2),
            'max_wait': round(df['Wait Time (min)'].max(), 2),
            'min_wait': round(df['Wait Time (min)'].min(), 2),
            'avg_service': round(df['Service Time (min)'].mean(), 2),
            'throughput_per_hour': round((len(df) / (df['Total Time'].sum() / 60)) * 100, 2) if df['Total Time'].sum() > 0 else 0
        }
        
        return jsonify({
            'metrics': metrics,
            'charts': {
                'box': fig_box.to_json(),
                'pie': fig_pie.to_json(),
                'line': fig_line.to_json()
            },
            'data': df.to_dict('records')
        })
    return jsonify({'error': 'No results available'}), 400


@app.route('/api/download', methods=['GET'])
def download_csv():
    """Download results as CSV."""
    if sim_state['result']:
        df = pd.read_json(sim_state['result'], orient='split')
        csv = df.to_csv(index=False)
        return csv, 200, {'Content-Disposition': 'attachment; filename=simulation_results.csv'}
    return jsonify({'error': 'No results available'}), 400


if __name__ == '__main__':
    app.run(debug=True, port=5000)
