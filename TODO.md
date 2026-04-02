# concepts
- limit hitting to horizontal range around body by checking orientation window (and possibly other instruments in other windows? (e.g. shakers when hands are up))
- "virtual controllers" separated by range?
- send "test" signals for learning midi
- mute controllers
- config: all params in config.yaml but nice UI and hot-updated!! (save & reload?)


# implementation
- Finish up threading refactor DONE
  - each ControllerState has its own lock
  - decide where `controllers` lives
  - Rework new controller / controller offline / remove controller / ... event flow
  - Check how the different threads access multiple controllers
  - Should the "main_loop" (currently processor thread) move?
- GUI
  - Make Controller cards more compact and flex list (grid / horizontal / ...); context menu for details, remove, etc
  - grey out inactive controllers
  - Bulk apply config   DONE

# BUGS
- Every now and again there is a massive random spike in accel or gyro data --> maybe we will need to bring back some kind of filter...
