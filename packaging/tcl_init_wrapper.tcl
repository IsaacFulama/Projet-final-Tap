# TAP bundles Tcl 8.6.15 from a Python installation whose Tcl_Init does not
# initialize tcl_library before sourcing init.tcl. Set it explicitly so Tk
# starts reliably on machines that do not have Python installed.
set ::tcl_library [file dirname [info script]]
source [file join $::tcl_library init_original.tcl]
