Option Explicit

Dim shell, files, root, python, url, command, ready, attempt, openBrowser

Set shell = CreateObject("WScript.Shell")
Set files = CreateObject("Scripting.FileSystemObject")

root = files.GetParentFolderName(WScript.ScriptFullName)
python = files.BuildPath(root, ".venv\Scripts\python.exe")
url = "http://127.0.0.1:8765/"
openBrowser = Not WScript.Arguments.Named.Exists("noopen")

If Not files.FileExists(python) Then
    MsgBox "Project environment is not installed. Run setup.ps1 first.", 16, "Recruiting Console"
    WScript.Quit 1
End If

ready = ServerReady(url)
If Not ready Then
    shell.CurrentDirectory = root
    command = Quote(python) & " -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8765"
    shell.Run command, 0, False

    For attempt = 1 To 50
        WScript.Sleep 200
        ready = ServerReady(url)
        If ready Then Exit For
    Next
End If

If Not ready Then
    MsgBox "The service failed to start. Use run.ps1 to view the error.", 16, "Recruiting Console"
    WScript.Quit 1
End If

If openBrowser Then shell.Run url, 1, False

Function Quote(value)
    Quote = Chr(34) & value & Chr(34)
End Function

Function ServerReady(address)
    Dim request
    ServerReady = False
    On Error Resume Next
    Set request = CreateObject("MSXML2.XMLHTTP")
    request.Open "GET", address, False
    request.Send
    If Err.Number = 0 Then ServerReady = (request.Status = 200)
    Err.Clear
    On Error GoTo 0
End Function
