from flask import Flask, render_template, request, jsonify, Response, send_file
from flask_cors import CORS
import pandas as pd
import json
import io
import plotly.graph_objects as go
import plotly.express as px
import plotly.io as pio
import zipfile
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

        # Try to create a real Excel workbook with native charts using XlsxWriter
        try:
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                # Write full data
                df.to_excel(writer, sheet_name='Data', index=False)

                workbook = writer.book
                data_ws = writer.sheets['Data']

                # Prepare helper columns for per-severity series
                start_col = df.shape[1] + 1  # place helpers after existing columns (1-based for xlsxwriter)
                # Column indices (0-based for pandas, xlsxwriter uses 0-based API in add_series)
                id_col = 0
                wait_col = df.columns.get_loc('Wait Time (min)')
                severity_col = df.columns.get_loc('Severity')

                # Build lists for each severity
                sev_labels = ["🔴 Emergency", "🟡 Urgent", "🟢 Non-Urgent"]
                helper_cols = {}
                for i, sev in enumerate(sev_labels):
                    col_name = f'Wait_{i}'
                    helper_cols[sev] = col_name
                    # compute series: value if severity matches else None
                    series_vals = [v if s == sev else None for v, s in zip(df['Wait Time (min)'], df['Severity'])]
                    # write column header and values starting at row 1
                    data_ws.write(0, df.shape[1] + i + 1, col_name)
                    for r, val in enumerate(series_vals, start=1):
                        data_ws.write(r, df.shape[1] + i + 1, val)

                # Also write aggregated throughput table for pie chart
                throughput = df['Severity'].value_counts().reindex(sev_labels).fillna(0).astype(int)
                tp_start_row = 1
                tp_col = df.shape[1] + len(sev_labels) + 3
                data_ws.write(0, tp_col, 'Severity')
                data_ws.write(0, tp_col + 1, 'Count')
                for i, sev in enumerate(sev_labels):
                    data_ws.write(i + 1, tp_col, sev)
                    data_ws.write(i + 1, tp_col + 1, int(throughput.get(sev, 0)))

                # Create a Charts sheet
                chart_ws = workbook.add_worksheet('Charts')

                # Line chart: separate series per severity
                line_chart = workbook.add_chart({'type': 'line'})
                nrows = len(df)
                for i, sev in enumerate(sev_labels):
                    col_idx = df.shape[1] + i + 1
                    # categories: IDs in column A (row 2..)
                    line_chart.add_series({
                        'name':       sev,
                        'categories': ['Data', 1, id_col, nrows, id_col],
                        'values':     ['Data', 1, col_idx, nrows, col_idx],
                        'marker': {'type': 'circle'},
                    })
                line_chart.set_title({'name': 'Wait Times Over Simulation'})
                line_chart.set_x_axis({'name': 'ID'})
                line_chart.set_y_axis({'name': 'Wait Time (min)'})
                chart_ws.insert_chart('A1', line_chart, {'x_scale': 1.5, 'y_scale': 1.0})

                # Pie chart for throughput
                pie_chart = workbook.add_chart({'type': 'pie'})
                pie_chart.add_series({
                    'name': 'Patient Throughput',
                    'categories': ['Data', tp_start_row, tp_col, tp_start_row + len(sev_labels) - 1, tp_col],
                    'values': ['Data', tp_start_row, tp_col + 1, tp_start_row + len(sev_labels) - 1, tp_col + 1],
                })
                pie_chart.set_title({'name': 'Patient Throughput'})
                chart_ws.insert_chart('A20', pie_chart, {'x_scale': 1.0, 'y_scale': 1.0})

                writer.save()
                output.seek(0)

            return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', as_attachment=True, download_name='simulation_results.xlsx')
        except Exception:
            # Fall back to ZIP with images if XlsxWriter not available or chart creation fails
            zip_buf = io.BytesIO()
            with zipfile.ZipFile(zip_buf, mode='w', compression=zipfile.ZIP_DEFLATED) as z:
                z.writestr('simulation_results.csv', csv_bytes)
                z.writestr('README.txt', 'Could not create native Excel charts. Install XlsxWriter and try again.')
            zip_buf.seek(0)
            return send_file(zip_buf, mimetype='application/zip', as_attachment=True, download_name='simulation_results_fallback.zip')
    return jsonify({'error': 'No results available'}), 400


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    app.run(debug=debug, port=port, host='0.0.0.0')
