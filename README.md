MyPy Utils: My Myth Python utils
==================================

MyPy contains My utitities for MythTV in python.

mfs.py is yet another implementation of file-system access to MythTV
(All the good names were taken).

mythbrake.py transcodes recordings. Either as a userjob or on
recordings that have 2 cutpoints.

mfs.py
------

All the versions of mythfs (python and C) i could find floating around
on the web were broken some way or another. Most commonly out-of-date
protocol, out-of-date bindings or broken i18N (which matters to me, I
am danish).

I took some inspiration from
https://github.com/wagnerrp/mythtv-scripts, but use a different style.

*Todo*

* An "update" file, so that read/write will update the fs
* Background thread update
* Prettier update code (perhaps update-id and added/removed events)



mythbrake.py
------------

None of the existing transcoding scripts for myth fitted my needs:

* Use some of the new-fangled encodings (H.264)
* Include subtitles from DVB recordings in DVB-SUB format (DVB in .dk)
* Use cut-points to remove start & end
* Ability to run "automatically" when start & end cut-points were set

*Todo*

* Inspect handbrake output to detect successful or failed transcode

Warning
-------

I tried to be *really* careful about deleting stuff in
mythbrake. Unfortunately handbrake exists 0 if it is terminated by a
signal which means it is very hard to reliably detect that a transcode
went OK.

STATE
-----

The code works for me.

TODO
----

* Refactor code to remove duplication
* Refactor to make the utility classes generally useful



