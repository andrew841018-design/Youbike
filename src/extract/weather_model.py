from typing import Annotated,List,Literal,Optional
from pydantic import BaseModel,ConfigDict,Field,TypeAdapter,AliasPath,BeforeValidator,AwareDatetime
from src.extract.weather_code import weather_error_code,codes
def transform_invalid_code(code):
    if code in codes:
        return None
    return code
def keep_error_code(code):
    if code in codes:
        return code
    return None
class Weather_Station(BaseModel):
    model_config = ConfigDict()
    station_id: str = Field(alias="StationId", pattern=r"\S", description="Station number")# non-empty string
    observe_time: AwareDatetime = Field(validation_alias=AliasPath("ObsTime", "DateTime"), description="observe time")  # must include timezone
    Latitude: float = Field(validation_alias=AliasPath("GeoInfo", "Coordinates", 1, "StationLatitude"))
    Longitude: float = Field(validation_alias=AliasPath("GeoInfo", "Coordinates", 1, "StationLongitude"))
    coordinate_name: Literal["WGS84"] = Field(validation_alias=AliasPath("GeoInfo", "Coordinates", 1, "CoordinateName"))
    Temperature: Annotated[Optional[float], BeforeValidator(transform_invalid_code)] = Field(validation_alias=AliasPath("WeatherElement", "AirTemperature"))
    Temperature_code: Annotated[Optional[weather_error_code], BeforeValidator(keep_error_code)] = Field(validation_alias=AliasPath("WeatherElement", "AirTemperature")) 
    Humidity: Annotated[Optional[float], BeforeValidator(transform_invalid_code)] = Field(validation_alias=AliasPath("WeatherElement", "RelativeHumidity"))
    Humidity_code: Annotated[Optional[weather_error_code], BeforeValidator(keep_error_code)] = Field(validation_alias=AliasPath("WeatherElement", "RelativeHumidity"))
    WindSpeed: Annotated[Optional[float], BeforeValidator(transform_invalid_code)] = Field(validation_alias=AliasPath("WeatherElement", "WindSpeed"))
    WindSpeed_code: Annotated[Optional[weather_error_code], BeforeValidator(keep_error_code)] = Field(validation_alias=AliasPath("WeatherElement", "WindSpeed"))
    Pressure: Annotated[Optional[float], BeforeValidator(transform_invalid_code)] = Field(validation_alias=AliasPath("WeatherElement", "AirPressure"))
    Pressure_code: Annotated[Optional[weather_error_code], BeforeValidator(keep_error_code)] = Field(validation_alias=AliasPath("WeatherElement", "AirPressure"))
    Precipitation: Annotated[Optional[float], BeforeValidator(transform_invalid_code)] = Field(validation_alias=AliasPath("WeatherElement", "Now", "Precipitation"))
    Precipitation_code: Annotated[Optional[weather_error_code], BeforeValidator(keep_error_code)] = Field(validation_alias=AliasPath("WeatherElement", "Now", "Precipitation"))
        
        
""" check every station at same time, each station is on the list"""
Weather_Stations = TypeAdapter(Annotated[List[Weather_Station], Field(min_length=1)])

""" whole response: official publish time (cwaopendata.sent) + every station """
class Weather_Response(BaseModel):
    published_at: AwareDatetime = Field(validation_alias=AliasPath("cwaopendata", "sent"), description="official publish time")
    stations: List[Weather_Station] = Field(validation_alias=AliasPath("cwaopendata", "dataset", "Station"), min_length=1, description="every station in this response")
