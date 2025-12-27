Set WshShell = CreateObject("WScript.Shell")

' Get script directory
scriptDir = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)

' Change to script directory
WshShell.CurrentDirectory = scriptDir

' Set Python path
WshShell.Environment("Process").Item("PYTHONPATH") = scriptDir

' Start Backend Server Window
WshShell.Run "cmd /k ""cd /d """ & scriptDir & """ && set PYTHONPATH=" & scriptDir & " && python -m uvicorn server.main:app --host 0.0.0.0 --port 5000""", 1, False

' Wait 3 seconds
WScript.Sleep 3000

' Start Frontend Server Window
WshShell.Run "cmd /k ""cd /d """ & scriptDir & "\client"" && npm run dev", 1, False

' Wait 3 seconds
WScript.Sleep 3000

' Start Status Monitor Window
statusScript = "echo ========================================" & vbCrLf & _
               "echo   Virginia Legal AI - Status Monitor" & vbCrLf & _
               "echo ========================================" & vbCrLf & _
               "echo." & vbCrLf & _
               "echo System Status:" & vbCrLf & _
               "echo." & vbCrLf & _
               "echo Backend:  http://localhost:5000" & vbCrLf & _
               "echo Frontend: http://localhost:3000" & vbCrLf & _
               "echo." & vbCrLf & _
               "echo Checking services every 5 seconds..." & vbCrLf & _
               "echo." & vbCrLf & _
               ":loop" & vbCrLf & _
               "timeout /t 5 /nobreak >nul" & vbCrLf & _
               "curl -s http://localhost:5000/health >nul 2>&1" & vbCrLf & _
               "if errorlevel 1 (echo [%time%] Backend: NOT RUNNING) else (echo [%time%] Backend: RUNNING)" & vbCrLf & _
               "curl -s http://localhost:3000 >nul 2>&1" & vbCrLf & _
               "if errorlevel 1 (echo [%time%] Frontend: NOT RUNNING) else (echo [%time%] Frontend: RUNNING)" & vbCrLf & _
               "echo." & vbCrLf & _
               "goto loop"

WshShell.Run "cmd /k """ & statusScript & """", 1, False

' Show completion message
WScript.Sleep 2000
MsgBox "Virginia Legal AI System Started!" & vbCrLf & vbCrLf & _
       "Three windows have been opened:" & vbCrLf & _
       "1. Backend Server (Port 5000)" & vbCrLf & _
       "2. Frontend Server (Port 3000)" & vbCrLf & _
       "3. Status Monitor" & vbCrLf & vbCrLf & _
       "Access the system at: http://localhost:3000" & vbCrLf & vbCrLf & _
       "To stop, close all three windows.", vbInformation, "Virginia Legal AI"

