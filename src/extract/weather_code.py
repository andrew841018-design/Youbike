import enum
class weather_error_code(str,enum.Enum):
    missing_value_or_invalid_data = "-99"
    equipment_failure = "X"
    no_precip_for_6h = "-98"
    trace_rain = "T"
