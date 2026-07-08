from flask import request
from flask_openapi3 import Tag, APIBlueprint

from app.config import API_PREFIX, API_VERSION
from app.dto.data_filters import PlantingDataFilter
from app.dto.planting_recommendation import PlantingRecommendationRecord, PlantingRecommendationResponse, Unauthorized
from app.repo.planting_recommendation import PlantingRecommendationRepo
from app.utils.logging import SharedLogger

__bp__ = "/planting-data"
url_prefix = API_PREFIX + API_VERSION + __bp__

tag = Tag(name="kvuno", description="Data serving API")

api = APIBlueprint(__bp__, __name__, url_prefix=url_prefix, abp_tags=[tag])

shared_logger = SharedLogger()
logger = shared_logger.get_logger()

repo = PlantingRecommendationRepo()


@api.get('',
         responses={200: PlantingRecommendationResponse, 401: Unauthorized})
def get_data(query: PlantingDataFilter):
    page = int(request.args.get('page', default=1, type=int))
    per_page = int(request.args.get('per_page', default=50, type=int))

    try:
        paginated_data = repo.get_paginated_data(query, page, per_page)

        data = [PlantingRecommendationRecord(
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
        ).__dict__ for item in paginated_data.items]

        return {
            'data': data,
            'total': paginated_data.total,
            'pages': paginated_data.pages,
            'current_page': paginated_data.page,
            'per_page': paginated_data.per_page,
        }, 200

    except Exception as e:
        logger.error(f"Error retrieving planting recommendation data: {e}")
        return {'error': str(e)}, 500
