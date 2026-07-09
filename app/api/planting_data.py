import csv
import io
import json

from flask import request, Response, stream_with_context
from flask_openapi3 import Tag, APIBlueprint

from app.config import API_PREFIX, API_VERSION
from app.dto.data_filters import PlantingDataFilter
from app.dto.planting_recommendation import PlantingRecommendationRecord, PlantingRecommendationResponse, Unauthorized
from app.repo.planting_recommendation import PlantingRecommendationRepo
from app.utils.logging import SharedLogger
from pydantic import BaseModel, Field

__bp__ = "/planting-data"
url_prefix = API_PREFIX + API_VERSION + __bp__

tag = Tag(name="kvuno", description="Data serving API")

api = APIBlueprint(__bp__, __name__, url_prefix=url_prefix, abp_tags=[tag])

shared_logger = SharedLogger()
logger = shared_logger.get_logger()

repo = PlantingRecommendationRepo()

EXPORT_COLUMNS = ['country', 'province', 'lon', 'lat', 'variety', 'season_type', 'opt_date', 'planting_option']


class CoordinatesResponse(BaseModel):
    coordinates: list[dict] = Field(default=[], description="Array of {lat, lon} objects")


@api.get('',
         responses={200: PlantingRecommendationResponse, 401: Unauthorized})
def get_data(query: PlantingDataFilter):
    page = int(request.args.get('page', default=1, type=int))
    per_page = int(request.args.get('per_page', default=50, type=int))

    try:
        paginated_data = repo.get_paginated_data(query, page, per_page)

        records = [PlantingRecommendationRecord(
            id=item.id,
            country=item.country,
            province=item.province,
            lon=item.lon,
            lat=item.lat,
            variety=item.variety,
            season_type=item.season_type,
            opt_date=item.opt_date,
            planting_option=item.planting_option,
            check_sum=item.check_sum,
            coordinates=str(item.coordinates),
        ) for item in paginated_data.items]

        return PlantingRecommendationResponse(
            data=records,
            total=paginated_data.total,
            pages=paginated_data.pages,
            current_page=paginated_data.page,
            per_page=paginated_data.per_page,
        ).model_dump(), 200

    except Exception as e:
        logger.error(f"Error retrieving planting recommendation data: {e}")
        return {'error': str(e)}, 500


FILTER_COLUMNS = ['country', 'province', 'variety', 'season_type']


@api.get('/filters')
def get_filter_options():
    try:
        values = repo.get_distinct_values(FILTER_COLUMNS)
        return values, 200
    except Exception as e:
        logger.error(f"Error fetching filter options: {e}")
        return {'error': str(e)}, 500


@api.get('/coordinates',
         responses={200: CoordinatesResponse, 401: Unauthorized})
def get_coordinates(query: PlantingDataFilter):
    try:
        points = repo.get_coordinates(query)
        return {"coordinates": [{"lat": lat, "lon": lon} for lat, lon in points]}, 200
    except Exception as e:
        logger.error(f"Error retrieving coordinates: {e}")
        return {'error': str(e)}, 500


def _row_to_dict(row):
    return {col: getattr(row, col, None) for col in EXPORT_COLUMNS}


@api.get('/export')
def export_data(query: PlantingDataFilter):
    fmt = request.args.get('format', 'csv')

    try:
        rows = repo.get_filtered_data(query)

        if fmt == 'json':
            def generate_json():
                yield '[\n'
                first = True
                for batch in rows.yield_per(500):
                    d = _row_to_dict(batch)
                    line = json.dumps(d, default=str)
                    if not first:
                        yield ',\n'
                    yield line
                    first = False
                yield '\n]\n'

            return Response(
                stream_with_context(generate_json()),
                mimetype='application/json',
                headers={'Content-Disposition': 'attachment; filename=kvuno-export.json'},
            )

        def generate_csv():
            buf = io.StringIO()
            w = csv.writer(buf)
            w.writerow(EXPORT_COLUMNS)
            yield buf.getvalue()
            buf.seek(0)
            buf.truncate(0)
            for batch in rows.yield_per(500):
                w.writerow([getattr(batch, col, None) or '' for col in EXPORT_COLUMNS])
                yield buf.getvalue()
                buf.seek(0)
                buf.truncate(0)

        return Response(
            stream_with_context(generate_csv()),
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment; filename=kvuno-export.csv'},
        )

    except Exception as e:
        logger.error(f"Error exporting data: {e}")
        return {'error': str(e)}, 500
