MyPy Utils: My Myth Python utils
==================================

MyPy contains My utitities for MythTV in python.

* mfs.py is yet another implementation of file-system access to MythTV
  (All the good names were taken).
* mythbrake.py transcodes recordings. Either as a userjob or on
  recordings that have 2 cutpoints.
* powermyth integrates with acpi to control poweroff behaviour to 
  * Prevent shutdown during recording
  * Set RTC wakeup to start the machine before next recording
