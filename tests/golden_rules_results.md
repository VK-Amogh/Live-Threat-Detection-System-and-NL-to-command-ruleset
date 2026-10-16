# Golden rule compiler results

Measured against the local configured LLM and detector class list.

1. PASS (20.1s): Alert when a person is in driveway.
   - Alert when a tracked person is inside driveway.

2. PASS (16.7s): Alert when a car is in driveway.
   - Alert when a tracked car is inside driveway.

3. PASS (25.0s): Alert me when a person stays in the driveway for 3 seconds between midnight and 5 a.m.
   - Alert when a tracked person between 00:00 and 05:00 Asia/Kolkata and remains there for at least 3 seconds and is inside driveway.

4. PASS (20.9s): Notify when a person is visible.
   - Alert when a tracked person is visible.

5. PASS (19.4s): Notify when a truck is visible.
   - Alert when a tracked truck is visible.

6. PASS (15.1s): Alert when a person crosses the gate line.
   - Alert when a tracked person crosses gate.

7. PASS (14.3s): Alert if at least four people cross gate within 60 seconds.
   - Alert when a tracked person at least 4 distinct tracks cross gate within 60 seconds.

8. PASS (15.4s): Alert when a person moves toward the driveway.
   - Alert when a tracked person moves toward driveway.

9. PASS (19.3s): Alert when a person is within 2 metres of driveway.
   - Metre distance needs camera homography calibration

10. PASS (20.6s): Alert when a person is in porch between 20:00 and 22:00.
   - Alert when a tracked person is inside porch between 20:00 and 22:00 Asia/Kolkata.

11. PASS (24.8s): Alert when a person enters driveway or porch.
   - Alert when a tracked person (is inside driveway or is inside porch).

12. PASS (27.7s): Alert when no person is visible.
   - Alert when a tracked person not (is visible).

13. PASS (16.4s): Alert if a person stays in porch for 5 seconds.
   - Alert when a tracked person remains there for at least 5 seconds and is inside porch.

14. PASS (22.1s): Alert if a car crosses the gate line between 01:00 and 02:00.
   - Alert when a tracked car crosses gate between 01:00 and 02:00 Asia/Kolkata.

15. PASS (12.4s): Alert when a bicycle is in driveway.
   - Alert when a tracked bicycle is inside driveway.

16. PASS (0.0s): Tell me when someone scratches my car.
   - Requested action or intent has no supported detector

17. PASS (0.0s): Alert when people fight near my car.
   - Requested action or intent has no supported detector

18. PASS (0.0s): Alert when someone carries a red backpack.
   - Color attributes are not supported by object detection

19. PASS (0.0s): Alert when a person is in driveway at night.
   - Specify exact night hours

20. PASS (18.3s): Alert when a drone is visible.
   - Cannot express the requested entity 'drone' as it is not in the list of available detector classes.

Result: 20/20 schema valid; 20/20 correct (100%).
