<!-- Separates implemented move/turn planning from unverified live-Claude evidence. -->
# Stretch goal: visual path planning

Implemented: the Claude tool set is move, turn, pickup, drop and done. There is no
go_to tool, hidden waypoint planner or object-location endpoint. Claude receives
camera pixels, the typed instruction, optional single-ray depth, collision feedback,
permitted robot state and its own visual notes. It chooses move/turn actions.

The engine performs physical collision stops, backoff and bounded recovery turns.
Those reflex actions are logged separately; they do not choose a route to a named item.

Verified offline: tool-schema checks, HTTP boundary checks and scripted dummy delivery.
Pixel mode is a separate OpenCV TEST ONLY controller, not evidence of Claude reasoning.
Live Claude path planning and three successful commands: UNVERIFIED.

package_run.py generates a run-specific report from the actual submitted tool names,
actions and mode. Mentor review is required before claiming stretch-goal points.
