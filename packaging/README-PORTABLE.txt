IconReplacer - portable edition
===============================

Replace folder icons from Windows Explorer. No installer, no administrator rights,
no Python needed.

Quick start
-----------
1. Unzip this folder anywhere you can write to (for example C:\Tools\IconReplacer).
   Do not run it from inside the zip file.
2. Run IconReplacer.exe.
3. Add the Explorer right-click entry: Settings -> Explorer integration -> Register.
   (Command line alternative: iconreplacer-cli.exe --register)
4. Right-click a folder -> "Show more options" on Windows 11 -> Replace Icon.

The menu entry points to the exe in this folder. If you move the folder, register again
(the Settings page reports a stale entry).

Command line
------------
  iconreplacer-cli.exe --version      print the version
  iconreplacer-cli.exe --status       is the Explorer entry registered?
  iconreplacer-cli.exe --register     add the per-user Explorer entry (HKCU only)
  iconreplacer-cli.exe --unregister   remove it
IconReplacer.exe is the windowed program and prints nothing; iconreplacer-cli.exe
is the same program with a console, for scripts and terminals.

Your data
---------
Settings, caches and logs live in the "data" folder next to IconReplacer.exe when that
folder is writable, otherwise in %LOCALAPPDATA%\IconReplacer.

Removal
-------
1. Settings -> Explorer integration -> Unregister (or iconreplacer-cli.exe --unregister).
2. Delete this folder.
Nothing else is installed on your system.

Notes
-----
The executables are not code-signed, so Windows SmartScreen may warn on first start.
Windows system icons are referenced in place and never copied. See
THIRD_PARTY_NOTICES.md for license information and LICENSE (MIT) for this program.
