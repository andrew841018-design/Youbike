from typing import Annotated,List
from pydantic import BaseModel,ConfigDict,Field,TypeAdapter

class YoubikeStation(BaseModel):
    model_config = ConfigDict(strict=True)
    station_id: str = Field(alias="sno", pattern=r"\S", description="Station number")# non-empty string
    station_name: str = Field(alias="sna", pattern=r"\S", description="Station name")# non-empty string
    station_area: str = Field(alias="sarea", pattern=r"\S", description="Station area")
    latitude: float
    longitude: float
    quantity: int = Field(alias="Quantity", ge=0, description="Total quantity of bikes at the station")
    available_rent_bikes: int = Field(ge=0, description="Number of bikes available for rent")
    available_return_bikes: int = Field(ge=0, description="Number of bikes available for return")
    station_active: str = Field(alias="act", pattern=r"\S", description="Station active status")# non-empty string
    source_update_time: str = Field(alias="srcUpdateTime", pattern=r"\S", description="Source update time")# non-empty string

""" check every station at same time, each station is on the list"""
YoubikeStations = TypeAdapter(Annotated[List[YoubikeStation], Field(min_length=1)])
