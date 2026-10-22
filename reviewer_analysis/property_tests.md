# Fresh randomized policy execution
500/500 agreements; 0 counterexamples; seed 42;
timestamp 2026-10-20T22:37:48.150622+00:00; commit bb2d9e4b4703b8f59dcd6ef563df374fcbe79720. Artifacts `results\camera_ready\property_tests\cr-20261020T223734Z-ffdfff82`.
Generator: random.Random; independent draws schema-valid probability .85, expired .25,
component-match .80, signed .70. Not Hypothesis despite module header.
Oracle: explicit 16-row Boolean truth table; hash 47ba90b22b41ad190cb0a0349cb18d4c9f3dc2d72683eca0c5af8fd0fcc78463.
Signing not required: unsigned branch cannot yield VEX_UNSIGNED in this 500-case execution.
Oracle and implementation share designed precedence; this is consistency testing, not independent security validation.
Inputs are supplied Boolean flags, not end-to-end VEX parsing or cryptographic verification.

Observed generated Boolean combinations: 15/16 across schema_valid, expired, component_match, signed. This does not make unsigned rejection reachable when require_signing=false.
