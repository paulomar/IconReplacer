# Third-party notices

IconReplacer itself is MIT licensed (see `LICENSE`). The portable release bundles the
following third-party components.

## PySide6 and Qt (LGPL-3.0)

The release contains PySide6 (Qt for Python) and the Qt 6 libraries, licensed under the
GNU Lesser General Public License version 3 (LGPL-3.0). Copyright The Qt Company Ltd. and
other contributors.

- The Qt libraries are **dynamically linked**: they are shipped as separate DLLs and
  plugins inside the `_internal\PySide6` folder. You may replace them with your own
  build of a compatible Qt/PySide6 version.
- The corresponding source code is available from <https://download.qt.io/> (Qt) and
  <https://code.qt.io/cgit/pyside/pyside-setup.git/> (PySide6). The license texts are at
  <https://www.gnu.org/licenses/lgpl-3.0.html> and <https://www.qt.io/licensing/>.
- IconReplacer does not modify Qt or PySide6.

## Python (PSF License)

The Python runtime (`python3xx.dll` and the standard library) is distributed under the
Python Software Foundation License, <https://docs.python.org/3/license.html>.

## PyInstaller

The executables are produced with PyInstaller (GPL-2.0-or-later with a special exception
that permits distributing the generated executables under any license). The bootloader
exception applies to `IconReplacer.exe` and `iconreplacer-cli.exe`; no PyInstaller code
other than the bootloader and its runtime hooks is included. See
<https://pyinstaller.org/en/stable/license.html>.

## Icon sources and artwork

- The application icon is original artwork drawn by code in this repository (MIT).
- **Microsoft icons** (Windows system DLL libraries such as `imageres.dll`) are never
  copied or redistributed. They are referenced in place on your computer by resource ID
  and read at run time only.
- Icon sets from online sources keep their own licenses. Repositories that declare no
  license are never bundled and are downloaded only on explicit user request; you are
  responsible for complying with the license of any icon you apply.
