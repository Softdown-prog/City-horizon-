// Deterministic weather adapter for headless UI proof executables.
//
// Production ui_manager.cpp deliberately queries weather through this narrow
// function boundary. The visual-capture targets do not run the simulation or
// weather system, so pin the proof to the canonical sunny state instead of
// linking unrelated runtime systems into a UI-only regression harness.
int ch_weather_ui_state_code() {
    return 0;  // WeatherUiState::sun
}
