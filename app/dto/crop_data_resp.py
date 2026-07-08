from typing import List, Optional

from pydantic import Field, BaseModel


class Unauthorized(BaseModel):
    code: int = Field(-1, description="Status Code", examples=[-1])
    message: str = Field("Unauthorized!", description="Exception Information", examples=["Unauthorized!"])


class CropDataRecord(BaseModel):
    id: Optional[int] = Field(default=None, description="Record ID", examples=[1])
    lat: Optional[float] = Field(default=None, description="Latitude", examples=[-1.29])
    lon: Optional[float] = Field(default=None, description="Longitude", examples=[36.82])
    country: Optional[str] = Field(default=None, description="Country", examples=["Kenya"])
    province: Optional[str] = Field(default=None, description="Province", examples=["Nairobi"])
    variety: Optional[str] = Field(default=None, description="Crop variety", examples=["H614"])
    season_type: Optional[str] = Field(default=None, description="Season type", examples=["Average"])
    opt_date: Optional[str] = Field(default=None, description="Optimal planting date", examples=["2024-10-15"])
    planting_option: Optional[int] = Field(default=None, description="Planting option", examples=[1])
    check_sum: Optional[str] = Field(default=None, description="File checksum", examples=["a1b2c3d4e5f6..."])
    coordinates: Optional[str] = Field(default=None, description="WKT coordinate string", examples=["POINT(36.82 -1.29)"])


class PlantingDataResponse(BaseModel):
    data: List[CropDataRecord] = Field(default=[], description="List of crop data records")
    total: int = Field(..., description="Total number of records", examples=[150])
    pages: int = Field(..., description="Total number of pages", examples=[3])
    current_page: int = Field(..., description="Current page number", examples=[1])
    per_page: int = Field(..., description="Records per page", examples=[50])
