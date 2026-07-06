import re
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict, field_validator


class PlantingDataFilter(BaseModel):
    coordinates: Optional[str] = Field(default=None, description='Coordinates in lon,lat format')
    radius: Optional[float] = Field(default=None, description='Radius to search from defined coordinates in meters')
    country: Optional[str] = Field(default=None, description='Country where the crop is located')
    province: Optional[str] = Field(default=None, description='Province where the crop is located')
    variety: Optional[str] = Field(default=None, description='Crop variety')
    season_type: Optional[str] = Field(default=None, description='Type of season, e.g., Average, High')
    opt_date: Optional[str] = Field(default=None, description='Optional date in YYYY-MM-DD format')
    planting_option: Optional[int] = Field(default=None, description='Option for planting, typically an integer')

    model_config = ConfigDict(
        use_enum_values=True,
        str_strip_whitespace=True
    )

    @field_validator('coordinates', mode='before')
    @classmethod
    def validate_coordinates(cls, value):
        """
        Validate the 'coordinates' field and ensure it's in 'lon,lat' format.
        Also validate that latitude and longitude are within valid ranges.
        """
        if value:
            # Validate that the coordinates are in 'lon,lat' format
            pattern = re.compile(r"^-?\d+(\.\d+)?,-?\d+(\.\d+)?$")
            if not pattern.match(value):
                raise ValueError("Coordinates must be in 'lon,lat' format.")

            # Split the coordinates into lon and lat
            lon_str, lat_str = value.split(',')

            # Convert to floats and validate ranges
            try:
                lon = float(lon_str)
                lat = float(lat_str)
            except ValueError:
                raise ValueError("Coordinates must contain valid float numbers.")

            if not (-90 <= lat <= 90):
                raise ValueError("Latitude must be between -90 and 90.")
            if not (-180 <= lon <= 180):
                raise ValueError("Longitude must be between -180 and 180.")
        return value

    @field_validator('opt_date', mode='before')
    @classmethod
    def validate_opt_date(cls, value):
        """
        Validate that the date is in 'YYYY-MM-DD' format.
        """
        if value:
            pattern = re.compile(r"^\d{4}-\d{2}-\d{2}$")
            if not pattern.match(value):
                raise ValueError("Date must be in 'YYYY-MM-DD' format.")
        return value
