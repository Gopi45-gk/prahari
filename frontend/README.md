# PRAHARI Command Center

## How to Run the Application

This application consists of a React Frontend and a FastAPI Backend. You need to run both to get the full functionality.

### 1. Run the Frontend
Open a new terminal (PowerShell or Command Prompt) and run the following commands:

```powershell
# Navigate to the frontend directory
cd "C:\Users\gopik\prahari-command"

# Start the frontend server
npm run dev
```
*The frontend will be available at http://localhost:5173*

### 2. Run the Backend
Open a **second, separate terminal** and run the following commands:

```powershell
# Navigate to the backend directory
cd "C:\Users\gopik\prahari-command\backend\api"

# Start the backend server
python main.py
```
*The backend API will run on http://localhost:8001*

---

**Note**: Do not type `cd"path" npm run dev` on a single line. The commands must be run on separate lines as shown above, or separated by a semicolon `;` in PowerShell.
