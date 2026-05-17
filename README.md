# HVAC Predictive Maintenance Demo Guide

This project is an end-to-end AI-driven Predictive Maintenance dashboard for Commercial HVAC chillers.

## 🔐 Default Credentials
When the frontend loads, use these details to log in to the dashboard:
* **Username:** `admin`
* **Password:** `admin123`

## 🚀 How to Run the Demo (Automated)

To easily start the entire stack (FastAPI Backend + React Frontend + Database Seeding), simply run this command from the project root:

```powershell
.\start_demo.ps1
```

This will automatically open separate terminal windows for the frontend and backend, and seed the initial baseline data.

## 🛠️ How to Run the Demo (Manual)

If you prefer to start the servers manually instead of using the script, you can do so:

**1. Start the Backend:**
```powershell
cd backend
py main.py
```

**2. Start the Frontend:**
Thanks to the wrapper script at the root, you do not need to navigate into the frontend folder. Just run this from the root directory:
```powershell
npm run dev
```

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
