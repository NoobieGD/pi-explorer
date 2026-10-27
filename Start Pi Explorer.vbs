Option Explicit
Dim shell, fs, root, python, command
Set shell = CreateObject("WScript.Shell")
Set fs = CreateObject("Scripting.FileSystemObject")
root = fs.GetParentFolderName(WScript.ScriptFullName)
python = root & "\.venv\Scripts\pythonw.exe"
command = Chr(34) & python & Chr(34) & " " & Chr(34) & root & "\server.py" & Chr(34)
shell.CurrentDirectory = root
shell.Run command, 0, False
