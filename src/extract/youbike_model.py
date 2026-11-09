from typing import Annotated,List
from pydantic import BaseModel,ConfigDict,Field,TypeAdapter

class YoubikeStation(BaseModel):
    model_config = ConfigDict(strict=True)
    sno: str = Field(pattern=r"\S", description="Station number")
    sna: str = Field(pattern=r"\S", description="Station name")
    sarea: str = Field(pattern=r"\S", description="Station area")
    latitude: float
    longitude: float
    Quantity: int = Field(ge=0, description="Total quantity of bikes at the station")
    available_rent_bikes: int = Field(ge=0, description="Number of bikes available for rent")
    available_return_bikes: int = Field(ge=0, description="Number of bikes available for return")
    act: str = Field(pattern=r"\S", description="Station active status")
    srcUpdateTime: str = Field(pattern=r"\S", description="Source update time")

YoubikeStations = TypeAdapter(Annotated[List[YoubikeStation], Field(min_length=1)])
