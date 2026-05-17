# HVAC Predictive Maintenance Demo Guide

This project is an end-to-end AI-driven Predictive Maintenance dashboard for Commercial HVAC chillers.

## 🚀 How to Run the Demo

To easily start the entire stack (FastAPI Backend + React Frontend + Database Seeding), simply run this command from the project root:

```powershell
.\start_demo.ps1
```

This will automatically open separate terminal windows for the frontend and backend, and seed the initial baseline data.

## ⚠️ How to Inject a Fault
To simulate a sudden critical failure (huge spikes in vibration, temperature, and power), run:

```powershell
py inject_fault.py
```
After running this, look at the React dashboard—you will see a sharp vertical climb in the sensor charts and a critical AI alert will be triggered.

## 🔄 How to Revert to Normal

You don't need to restart your servers to reset the demo! Simply run:

```powershell
py scripts\revert_db.py
```
This instantly drops the fault data from the database and reseeds it with clean baseline data. Your dashboard will automatically update on its next polling cycle.
