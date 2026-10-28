# Why Restart Was Not Simple (and How It Works Now)

## What was going wrong

### 1. Backend running as Administrator
**START_BACKEND.bat** used to request "Run as Administrator" so it could free port 5001. That meant the backend process (uvicorn) ran **as Administrator**. When you tried to restart from Cursor, a normal terminal, or **RESTART.bat** without admin, `taskkill` on that process returned **Access is denied** and the port stayed in use.

### 2. Two ways to start the backend
- **START_BACKEND.bat** – elevated, so the process was admin-owned and hard to kill without admin.
- **START_SYSTEM.bat** / **scripts\run_backend.bat** – not elevated, so the process could be killed by a normal user.

Depending on how you started the app, restart could or couldn’t free the port without admin.

### 3. PowerShell port check failing under load
**scripts\kill_port.ps1** used `Get-NetTCPConnection`, which can fail with **"The paging file is too small for this operation"** when the system is under memory pressure (e.g. after running Ollama). So the PowerShell-based kill was unreliable.

### 4. No single “restart” script
There was no one script that reliably stopped backend and frontend and then started them again. You had to close windows by hand or run several steps.

---

## What we changed

1. **START_BACKEND.bat** no longer requests admin. It still frees port 5001 using `netstat` + `taskkill` (CMD), so the backend runs as the **current user** and can be killed by a normal restart.
2. **scripts\kill_port.ps1** now has a **netstat fallback**: if `Get-NetTCPConnection` fails (e.g. paging file error), it finds PIDs with `netstat -ano` and kills them. So port freeing works even when PowerShell’s TCP cmdlets fail.
3. **RESTART.bat** (project root) does one thing: free ports 5001, 3000, and 3001 with `netstat` + `taskkill`, then start the backend and frontend in new windows. No admin required **if** the processes were started without admin (e.g. by **RESTART.bat** or **START_SYSTEM.bat** or **run_backend.bat**).

---

## How to restart now

**Preferred (no admin):**
1. Double-click **RESTART.bat** at the project root.  
   It will stop anything on 5001/3000/3001 (that you can kill), wait a few seconds, then open Backend and Frontend windows.

**If you see "Access denied" when freeing a port:**  
The process on that port was started as Administrator (e.g. an old **START_BACKEND.bat** run). Either:
- Close the Backend (or Frontend) window that’s using the port, then run **RESTART.bat** again, or  
- Right-click **RESTART.bat** → **Run as administrator** once to stop those processes; after that, use **RESTART.bat** normally.

**Starting fresh (no restart):**
- **START_SYSTEM.bat** – starts Backend and Frontend in two windows (no admin).  
- Or **START_BACKEND.bat** and **START_FRONTEND.bat** in two terminals (no admin).

---

## Summary

| Before | After |
|--------|--------|
| Backend often ran as admin → couldn’t kill without admin | Backend runs as current user → restart can kill it |
| PowerShell kill failed under memory load | kill_port.ps1 falls back to netstat so kill still works |
| No single restart script | **RESTART.bat** stops ports then starts both servers |

Restart is now: run **RESTART.bat** (or close the two server windows and run **START_SYSTEM.bat** again).
