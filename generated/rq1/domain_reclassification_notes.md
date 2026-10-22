# Domain Reclassification Notes

## Decision: Operating System
Windows is reclassified from HBOM (hardware) to OBOM (runtime/operational).
Rationale: An OS is software state, not a physical component.
CycloneDX representation: component type=operating-system.

## Decision: CPU
The processor is represented as a first-class HBOM device component.
Observable data: Intel64 Family 6 Model 181 Stepping 0, GenuineIntel
Cores: 12P/14T
Max freq: 2100.0 MHz
Not fabricated: serial number, firmware, exact model number.

## Decision: RAM
Physical memory remains an HBOM hardware component.
Observable: 31.5 GB total
Represented as CycloneDX device component with measured capacity.
