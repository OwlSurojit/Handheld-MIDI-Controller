# Installation (Development)
## For flashing the firmware
* Install PlatformIO VSCode extension
* On windows: [Enable long paths in git and on filesystem](https://arduino-pico.readthedocs.io/en/latest/platformio.html#important-steps-for-windows-users-before-installing)
* You might need to enable gpedit first:
  * `FOR %F IN ("%SystemRoot%\servicing\Packages\Microsoft-Windows-GroupPolicy-ClientTools-Package~*.mum") DO (DISM /Online /NoRestart /Add-Package:"%F")`
  * `FOR %F IN ("%SystemRoot%\servicing\Packages\Microsoft-Windows-GroupPolicy-ClientExtensions-Package~*.mum") DO (DISM /Online /NoRestart /Add-Package:"%F")`
* To flash you might need to install a WinUSB driver via [Zadig](https://zadig.akeo.ie/)

## For running the server
* Set up venv
* Install `requirements.txt`
* If installation of `python-rtmidi` fails (on Windows) --> Install Build Tools for Visual Studio:
  * Download [Visual Studio Installer](https://visualstudio.microsoft.com/downloads/)
  * Workload: Select "Desktop development with C++".
  * Components: Ensure the Windows 10 (or 11) SDK and MSVC v143 - VS 2022 C++ x64/x86 build tools are checked in the sidebar. 
* On windows: Install [loopMIDI](https://www.tobias-erichsen.de/software/loopmidi.html) and create a loopback MIDI port called "Handheld MIDI Controller"
* You might need to restart "Windows MIDI Service" in services