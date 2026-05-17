from flask import Flask, render_template, request, jsonify, Response, send_file
from flask_cors import CORS
import pandas as pd
import json
import io
import plotly.graph_objects as go
import plotly.express as px
import plotly.io as pio
import zipfile
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
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

            # Generate charts
            fig_box = px.box(preview_df, x='Severity', y='Wait Time (min)', color='Severity',
                             color_discrete_map={"🔴 Emergency": "red", "🟡 Urgent": "orange", "🟢 Non-Urgent": "green"},
                             title="Wait Time Distribution by Severity")

            throughput_df = df.groupby('Severity').size().reset_index(name='Count')
            fig_pie = px.pie(throughput_df, values='Count', names='Severity', hole=0.4,
                             color='Severity', color_discrete_map={"🔴 Emergency": "red", "🟡 Urgent": "orange", "🟢 Non-Urgent": "green"},
                             title="Patient Throughput")

            # Wait time over time (use preview for plotting density if needed)
            fig_line = px.line(preview_df.sort_values('ID'), x='ID', y='Wait Time (min)', 
                               color='Severity', title="Wait Times Over Simulation",
                               color_discrete_map={"🔴 Emergency": "red", "🟡 Urgent": "orange", "🟢 Non-Urgent": "green"})

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
                    'box': fig_box.to_json(),
                    'pie': fig_pie.to_json(),
                    'line': fig_line.to_json()
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

        # Create a PDF with the three charts and include the CSV in a ZIP for download
        try:
            # Export chart PNGs using kaleido
            box_png = pio.to_image(fig_box, format='png')
            pie_png = pio.to_image(fig_pie, format='png')
            line_png = pio.to_image(fig_line, format='png')

            # Build PDF with reportlab, one chart per page
            pdf_buf = io.BytesIO()
            c = canvas.Canvas(pdf_buf, pagesize=letter)
            width, height = letter
            margin = 40

            for title, img_bytes in [('Wait Time Distribution', box_png), ('Patient Throughput', pie_png), ('Wait Times Over Simulation', line_png)]:
                img = ImageReader(io.BytesIO(img_bytes))
                iw, ih = img.getSize()
                max_w = width - 2 * margin
                max_h = height - 2 * margin - 40
                scale = min(max_w / iw, max_h / ih, 1)
                draw_w, draw_h = iw * scale, ih * scale
                x = (width - draw_w) / 2
                y = (height - draw_h) / 2 - 20

                c.setFont('Helvetica-Bold', 14)
                c.drawCentredString(width / 2, height - margin, title)
                c.drawImage(img, x, y, width=draw_w, height=draw_h)
                c.showPage()

            c.save()
            pdf_buf.seek(0)

            # Create ZIP with PDF + CSV
            zip_buf = io.BytesIO()
            with zipfile.ZipFile(zip_buf, mode='w', compression=zipfile.ZIP_DEFLATED) as z:
                z.writestr('simulation_results.csv', csv_bytes)
                z.writestr('simulation_charts.pdf', pdf_buf.getvalue())

            zip_buf.seek(0)
            return send_file(zip_buf, mimetype='application/zip', as_attachment=True, download_name='simulation_results.zip')
        except Exception:
            # If PDF/chart generation fails, return CSV only
            csv_buf = io.BytesIO(csv_bytes)
            csv_buf.seek(0)
            return send_file(csv_buf, mimetype='text/csv', as_attachment=True, download_name='simulation_results.csv')
    return jsonify({'error': 'No results available'}), 400


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    app.run(debug=debug, port=port, host='0.0.0.0')
