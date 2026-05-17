from flask import Flask, render_template, request, jsonify, Response, send_file
from flask_cors import CORS
import pandas as pd
import json
import io
import plotly.graph_objects as go
import plotly.express as px
import zipfile
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import threading
import time
from datetime import datetime
import os

import simulation

app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False

# Enable CORS for GitHub Pages & remote deployments
CORS(app)

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
        try:
            # sim_state['result'] is a JSON string produced earlier; read it safely from a buffer
            buf = io.StringIO(sim_state['result'])
            df = pd.read_json(buf, orient='split')

            # Limit rows returned to avoid huge payloads to the browser
            preview_df = df.head(200)

            # Generate charts as plain Python lists (avoid Plotly bdata binary encoding)
            severity_order = ["🔴 Emergency", "🟡 Urgent", "🟢 Non-Urgent"]
            color_map = {"🔴 Emergency": "red", "🟡 Urgent": "orange", "🟢 Non-Urgent": "green"}

            # Box traces
            box_traces = []
            for s in severity_order:
                vals = preview_df[preview_df['Severity'] == s]['Wait Time (min)'].dropna().tolist()
                box_traces.append({
                    'type': 'box',
                    'name': s,
                    'y': vals,
                    'marker': {'color': color_map.get(s, 'grey')},
                    'boxmean': True
                })

            # Pie trace
            throughput = df['Severity'].value_counts().reindex(severity_order).fillna(0).astype(int)
            pie_trace = [{
                'type': 'pie',
                'labels': [s for s in severity_order],
                'values': throughput.tolist(),
                'marker': {'colors': [color_map[s] for s in severity_order]}
            }]

            # Line traces: one per severity, x=ID, y=Wait Time
            line_traces = []
            for s in severity_order:
                sub = preview_df[preview_df['Severity'] == s].sort_values('ID')
                xs = sub['ID'].tolist()
                ys = sub['Wait Time (min)'].tolist()
                line_traces.append({
                    'type': 'scatter',
                    'mode': 'lines+markers',
                    'name': s,
                    'x': xs,
                    'y': ys,
                    'marker': {'size': 6},
                    'line': {'color': color_map.get(s)}
                })

            # Layouts
            box_layout = {'title': 'Wait Time Distribution by Severity', 'yaxis': {'title': 'Wait Time (min)'}, 'xaxis': {'title': 'Severity'}}
            pie_layout = {'title': 'Patient Throughput'}
            line_layout = {'title': 'Wait Times Over Simulation', 'xaxis': {'title': 'ID'}, 'yaxis': {'title': 'Wait Time (min)'}}

            # Metrics (computed on full df)
            metrics = {
                'total_patients': int(len(df)),
                'avg_wait': round(df['Wait Time (min)'].mean(), 2) if not df.empty else 0,
                'max_wait': round(df['Wait Time (min)'].max(), 2) if not df.empty else 0,
                'min_wait': round(df['Wait Time (min)'].min(), 2) if not df.empty else 0,
                'avg_service': round(df['Service Time (min)'].mean(), 2) if not df.empty else 0,
                'throughput_per_hour': round((len(df) / (df['Total Time'].sum() / 60)) * 100, 2) if df['Total Time'].sum() > 0 else 0
            }

            return jsonify({
                'metrics': metrics,
                'charts': {
                    'box': {'data': box_traces, 'layout': box_layout},
                    'pie': {'data': pie_trace, 'layout': pie_layout},
                    'line': {'data': line_traces, 'layout': line_layout}
                },
                'data': preview_df.to_dict('records')
            })
        except Exception as e:
            return jsonify({'error': f'Failed to prepare results: {str(e)}'}), 500
    return jsonify({'error': 'No results available'}), 400


@app.route('/api/download', methods=['GET'])
def download_csv():
    """Download results as CSV."""
    if sim_state['result']:
        buf = io.StringIO(sim_state['result'])
        df = pd.read_json(buf, orient='split')
        # Build CSV bytes
        csv_bytes = df.to_csv(index=False).encode('utf-8')

        # Recreate charts (same as in /api/results)
        preview_df = df.head(200)
        fig_box = px.box(preview_df, x='Severity', y='Wait Time (min)', color='Severity',
                         color_discrete_map={"🔴 Emergency": "red", "🟡 Urgent": "orange", "🟢 Non-Urgent": "green"},
                         title="Wait Time Distribution by Severity")

        throughput_df = df.groupby('Severity').size().reset_index(name='Count')
        fig_pie = px.pie(throughput_df, values='Count', names='Severity', hole=0.4,
                         color='Severity', color_discrete_map={"🔴 Emergency": "red", "🟡 Urgent": "orange", "🟢 Non-Urgent": "green"},
                         title="Patient Throughput")

        fig_line = px.line(preview_df.sort_values('ID'), x='ID', y='Wait Time (min)',
                           color='Severity', title="Wait Times Over Simulation",
                           color_discrete_map={"🔴 Emergency": "red", "🟡 Urgent": "orange", "🟢 Non-Urgent": "green"})

        # Create a PDF with the three charts using matplotlib and include the CSV in a ZIP
        try:
            pdf_buf = io.BytesIO()
            with PdfPages(pdf_buf) as pdf:
                # Figure 1: Boxplot by Severity (styled to match web view)
                import numpy as np
                fig1, ax1 = plt.subplots(figsize=(8, 6))
                df_box = preview_df[['Severity', 'Wait Time (min)']]
                severity_order = ["🔴 Emergency", "🟡 Urgent", "🟢 Non-Urgent"]
                grouped = [df_box[df_box['Severity'] == s]['Wait Time (min)'].dropna().values for s in severity_order]
                # Replace empty groups with an array of NaN to avoid boxplot errors
                grouped_safe = [g if len(g) > 0 else np.array([np.nan]) for g in grouped]
                bplot = ax1.boxplot(grouped_safe, labels=[s.replace('🔴 ','').replace('🟡 ','').replace('🟢 ','') for s in severity_order], patch_artist=True, showfliers=True)
                # color boxes to match the site
                colors = ['red', 'orange', 'green']
                for patch, color in zip(bplot['boxes'], colors):
                    patch.set_facecolor(color)
                    patch.set_alpha(0.3)
                for median in bplot['medians']:
                    median.set_color('black')
                ax1.set_title('Wait Time Distribution by Severity')
                ax1.set_ylabel('Wait Time (min)')
                ax1.set_xlabel('Severity')
                pdf.savefig(fig1)
                plt.close(fig1)

                # Figure 2: Pie chart of throughput
                fig2, ax2 = plt.subplots(figsize=(8, 6))
                counts = df['Severity'].value_counts().reindex(severity_order).fillna(0)
                labels_clean = [s.replace('🔴 ','').replace('🟡 ','').replace('🟢 ','') for s in severity_order]
                ax2.pie(counts.values, labels=labels_clean, autopct='%1.1f%%', startangle=90)
                ax2.set_title('Patient Throughput')
                pdf.savefig(fig2)
                plt.close(fig2)

                # Figure 3: Line chart of wait time over ID (separate series)
                fig3, ax3 = plt.subplots(figsize=(10, 6))
                for s in severity_order:
                    sub = preview_df[preview_df['Severity'] == s].sort_values('ID')
                    if not sub.empty:
                        ax3.plot(sub['ID'], sub['Wait Time (min)'], marker='o', label=s.replace('🔴 ','').replace('🟡 ','').replace('🟢 ',''))
                ax3.set_title('Wait Times Over Simulation')
                ax3.set_xlabel('ID')
                ax3.set_ylabel('Wait Time (min)')
                ax3.legend()
                pdf.savefig(fig3)
                plt.close(fig3)

            pdf_buf.seek(0)

            # Create ZIP with PDF + CSV
            zip_buf = io.BytesIO()
            with zipfile.ZipFile(zip_buf, mode='w', compression=zipfile.ZIP_DEFLATED) as z:
                z.writestr('simulation_results.csv', csv_bytes)
                z.writestr('simulation_charts.pdf', pdf_buf.getvalue())

            zip_buf.seek(0)
            return send_file(zip_buf, mimetype='application/zip', as_attachment=True, download_name='simulation_results.zip')
        except Exception as e:
            # If PDF/chart generation fails, return CSV only and log the error
            print('Download PDF generation failed:', e)
            csv_buf = io.BytesIO(csv_bytes)
            csv_buf.seek(0)
            return send_file(csv_buf, mimetype='text/csv', as_attachment=True, download_name='simulation_results.csv')
    return jsonify({'error': 'No results available'}), 400


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    app.run(debug=debug, port=port, host='0.0.0.0')
