import simpy
import random
import pandas as pd


def run_simulation(num_doctors: int, avg_arrival: float, sim_time: float, seed: int | None = None) -> pd.DataFrame:
    """Run a single replication of the hospital triage simulation.

    Args:
        num_doctors: number of server resources
        avg_arrival: average minutes between arrivals (exponential mean)
        sim_time: total simulation time in minutes
        seed: optional RNG seed for reproducibility

    Returns:
        pandas.DataFrame with one row per patient and columns for metrics
    """
    rng = random.Random(seed)

    class Hospital:
        def __init__(self, env, num_doctors):
            self.env = env
            self.staff = simpy.PriorityResource(env, capacity=num_doctors)

    def patient_arrival(env, hospital, arrival_rate, data):
        patient_id = 0
        while True:
            yield env.timeout(rng.expovariate(1.0 / arrival_rate))
            patient_id += 1

            # Severity distribution
            severity_roll = rng.random()
            if severity_roll < 0.2:
                priority, label = 1, "🔴 Emergency"
            elif severity_roll < 0.5:
                priority, label = 2, "🟡 Urgent"
            else:
                priority, label = 3, "🟢 Non-Urgent"

            arrival_time = env.now
            env.process(treat_patient(env, hospital, patient_id, priority, label, arrival_time, data))

    def treat_patient(env, hospital, p_id, priority, label, arrival_time, data):
        with hospital.staff.request(priority=priority) as request:
            yield request
            wait_time = env.now - arrival_time

            # Service time (ensure positive)
            service_duration = max(1, rng.normalvariate(20, 5))
            yield env.timeout(service_duration)

            data.append({
                "ID": p_id,
                "Severity": label,
                "Wait Time (min)": round(wait_time, 2),
                "Service Time (min)": round(service_duration, 2),
                "Total Time": round(wait_time + service_duration, 2),
            })

    env = simpy.Environment()
    hospital = Hospital(env, num_doctors)
    records = []
    env.process(patient_arrival(env, hospital, avg_arrival, records))
    env.run(until=sim_time)

    df = pd.DataFrame(records)
    return df
