import streamlit as st
import simpy
import random
import pandas as pd
import plotly.express as px

# --- PAGE CONFIG (International UX: Clean & Responsive) ---
st.set_page_config(page_title="Hospital Triage Digital Twin", layout="wide")

# --- CUSTOM CSS FOR SLEEK UI ---
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    </style>
    """, unsafe_allow_html=True)

# --- SIMULATION LOGIC (SimPy) ---
class Hospital:
    def __init__(self, env, num_doctors):
        self.env = env
        self.staff = simpy.PriorityResource(env, capacity=num_doctors)

def patient_arrival(env, hospital, arrival_rate, data):
    patient_id = 0
    while True:
        # Stochastic Arrival (Exponential Distribution)
        yield env.timeout(random.expovariate(1.0 / arrival_rate))
        patient_id += 1
        
        # Determine Severity (1=Highest, 3=Lowest) - Monte Carlo technique
        severity_roll = random.random()
        if severity_roll < 0.2:
            priority, label, color = 1, "🔴 Emergency", "red"
        elif severity_roll < 0.5:
            priority, label, color = 2, "🟡 Urgent", "orange"
        else:
            priority, label, color = 3, "🟢 Non-Urgent", "green"
        
        arrival_time = env.now
        env.process(treat_patient(env, hospital, patient_id, priority, label, arrival_time, data))

def treat_patient(env, hospital, p_id, priority, label, arrival_time, data):
    with hospital.staff.request(priority=priority) as request:
        yield request
        wait_time = env.now - arrival_time
        
        # Service Time (Normal Distribution)
        service_duration = max(1, random.normalvariate(20, 5))
        yield env.timeout(service_duration)
        
        data.append({
            "ID": p_id,
            "Severity": label,
            "Wait Time (min)": round(wait_time, 2),
            "Service Time (min)": round(service_duration, 2),
            "Total Time": round(wait_time + service_duration, 2)
        })

# --- STREAMLIT UI ---
st.title("🏥 Hospital Triage: Computational Model")
st.markdown("An integrated modeling approach for system performance analysis.")

# Sidebar for Experiment Design & Control 
with st.sidebar:
    st.header("⚙️ Simulation Parameters")
    num_doctors = st.slider("Number of Staff Available", 1, 10, 3)
    avg_arrival = st.slider("Avg Minutes Between Arrivals", 1, 30, 10)
    sim_time = st.number_input("Simulation Run Time (mins)", value=480)
    
    run_sim = st.button("🚀 Run Simulation")

if run_sim:
    # Initialize Simulation
    env = simpy.Environment()
    hospital = Hospital(env, num_doctors)
    sim_data = []
    
    # Run the process
    env.process(patient_arrival(env, hospital, avg_arrival, sim_data))
    env.run(until=sim_time)
    
    # Process Results 
    df = pd.DataFrame(sim_data)
    
    if not df.empty:
        # Top Row Metrics (UX: Visibility of System Status)
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Patients Treated", len(df))
        c2.metric("Avg Wait Time", f"{round(df['Wait Time (min)'].mean(), 2)} min")
        c3.metric("Max Wait Time", f"{round(df['Wait Time (min)'].max(), 2)} min")
        
        st.divider()
        
        # Data Visualization
        col_left, col_right = st.columns(2)
        
        with col_left:
            st.subheader("Wait Time by Severity")
            fig_box = px.box(df, x="Severity", y="Wait Time (min)", color="Severity",
                            color_discrete_map={"🔴 Emergency": "red", "🟡 Urgent": "orange", "🟢 Non-Urgent": "green"})
            st.plotly_chart(fig_box, use_container_width=True)
            
        with col_right:
            st.subheader("Patient Throughput")
            throughput_df = df.groupby("Severity").count().reset_index()
            fig_pie = px.pie(throughput_df, values="ID", names="Severity", hole=0.4,
                            color="Severity", color_discrete_map={"🔴 Emergency": "red", "🟡 Urgent": "orange", "🟢 Non-Urgent": "green"})
            st.plotly_chart(fig_pie, use_container_width=True)

        st.subheader("Detailed Raw Logs")
        st.dataframe(df, use_container_width=True)
    else:
        st.warning("No data generated. Try increasing simulation time or arrival rates.")

else:
    st.info("Adjust the parameters in the sidebar and click 'Run Simulation' to begin.")