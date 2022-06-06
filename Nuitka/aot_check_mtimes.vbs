name = WScript.Arguments(0)
set fs = CreateObject ("Scripting.FileSystemObject")

last_compile_time = fs.GetFile(name & ".dist\" & name & ".exe").DateLastModified

Function walk(folder)
  For each file in folder.Files
    If Right(file.Path, 3) = ".py" Then
      If file.DateLastModified >= last_compile_time Then
        WScript.Quit 1
      End If
    End If
  Next

  For each sub_folder in folder.Subfolders
    walk(sub_folder)
  Next
End Function

walk(fs.GetFolder("."))
WScript.Quit 0
