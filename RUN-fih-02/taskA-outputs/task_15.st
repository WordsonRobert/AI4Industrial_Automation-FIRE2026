PROGRAM compressorMotorControl
VAR_INPUT
    pressure_sensor : INT;
END_VAR
VAR_OUTPUT
    compressor_motor : BOOL;
END_VAR
compressor_motor := pressure_sensor >= 120 OR pressure_sensor <= 80;
END_PROGRAM