Set WshShell = CreateObject("WScript.Shell")
' 0 = Hide window, False = Do not wait for completion
WshShell.Run "cmd /c python launcher.py", 0, False
Set WshShell = Nothing
